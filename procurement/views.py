from django.shortcuts import render, redirect, get_object_or_404
from decimal import Decimal
from django.views import generic, View
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils import timezone
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView
from django.views.generic import DetailView
from django.db.models import Q, Exists, OuterRef
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST
from .models import Signatory
import csv
from django.http import HttpResponse
from .utils import award_aoq_and_create_po
from django.views.decorators.csrf import csrf_exempt
import json

from .models import (
    PurchaseRequest, PRItem, Supplier,
    RequestForQuotation, AgencyProcurementRequest,
    AbstractOfQuotation, AOQLine, PurchaseOrder, Bid, BidLine
)
from .forms import (
    RequisitionerPRForm, ProcurementStaffPRForm,
    PRItemFormSet, SupplierForm,
    RFQForm, APRForm, AOQLineFormSet, PurchaseOrderForm,
    AssignPRNumberForm, BidForm, BidLineForm, BidLineFormSet, RFQConsolidationLog
)

def rfq_pr_items(rfq):
    """Return all PRItems linked to this RFQ, whether single or consolidated."""
    if hasattr(rfq, "consolidated_prs") and rfq.consolidated_prs.exists():
        # ✅ Consolidated RFQ: many-to-many relationship used
        return PRItem.objects.filter(purchase_request__in=rfq.consolidated_prs.all())
    elif hasattr(rfq, "purchase_request") and rfq.purchase_request:
        # ✅ Regular RFQ: one-to-one (or foreign key) used
        return PRItem.objects.filter(purchase_request=rfq.purchase_request)
    else:
        return PRItem.objects.none()



# -----------------------
# USER GROUP CHECKS
# -----------------------
def in_procurement_group(user):
    return user.is_authenticated and user.groups.filter(name="Procurement").exists()

def in_requisitioner_group(user):
    return user.is_authenticated and user.groups.filter(name="Requisitioner").exists()

# -----------------------
# DASHBOARD
# -----------------------
class DashboardView(LoginRequiredMixin, generic.TemplateView):
    template_name = "procurement/dashboard.html"

    def get_template_names(self):
        user = self.request.user
        if user.groups.filter(name="Admin").exists():
            return ["procurement/dashboard_admin.html"]
        elif user.groups.filter(name="Procurement").exists():
            return ["procurement/dashboard_procurement.html"]
        elif user.groups.filter(name="Requisitioner").exists():
            return ["procurement/dashboard_requisitioner.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Base queries
        pr_qs = PurchaseRequest.objects.all()

        # Default counts (Admin/Procurement see everything)
        unassigned_filter = Q(pr_number__isnull=True) | Q(pr_number__exact='') | Q(pr_number__iexact='Unassigned')
        assigned_filter = ~unassigned_filter

        # --- Requisitioner-specific filtering ---
        if user.groups.filter(name="Requisitioner").exists():
            # Only their own PRs
            user_prs = pr_qs.filter(created_by=user)
            # Unassigned PRs (no PR number)
            context["unassigned_pr_count"] = user_prs.filter(unassigned_filter).count()
            # In Progress PRs: must HAVE pr_number + optional status
            context["pr_count"] = user_prs.filter(assigned_filter).count()
        else:
            # Admin / Procurement see all
            context["unassigned_pr_count"] = pr_qs.filter(unassigned_filter).count()
            context["pr_count"] = pr_qs.filter(assigned_filter).count()

        # Other counts remain global (you can scope them too if you like)
        context["rfq_count"] = RequestForQuotation.objects.count()
        context["aoq_count"] = AbstractOfQuotation.objects.count()
        context["po_count"] = PurchaseOrder.objects.count()

        # Dashboard label
        if user.groups.filter(name="Procurement").exists():
            context["welcome_text"] = "Procurement Officer Dashboard"
        elif user.groups.filter(name="Requisitioner").exists():
            context["welcome_text"] = "Requisitioner Dashboard"
        elif user.groups.filter(name="Admin").exists():
            context["welcome_text"] = "Admin Dashboard"
        else:
            context["welcome_text"] = "User Dashboard"

        return context


@login_required
def requisitioner_dashboard(request):
    # Get PRs created by the logged-in user
    user_prs = PurchaseRequest.objects.filter(created_by=request.user)

    # Count unassigned PRs (no PR number)
    unassigned_count = user_prs.filter(pr_number__isnull=True).count()

    # Count PRs that are already submitted or under review
    in_progress_count = user_prs.filter(status__in=["For Verification", "Under Review", "Processing"]).count()

    context = {
        "unassigned_count": unassigned_count,
        "in_progress_count": in_progress_count,
    }

    return render(request, "procurement/requisitioner_dashboard.html", context)


# -----------------------
# PURCHASE REQUEST VIEWS
# -----------------------
class PRListView(LoginRequiredMixin, generic.ListView):
    model = PurchaseRequest
    template_name = "procurement/pr_list.html"
    context_object_name = "prs"
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        unassigned_q = (
            Q(pr_number__isnull=True)
            | Q(pr_number__exact="")
            | Q(pr_number__iexact="Unassigned")
        )
        queryset = PurchaseRequest.objects.all()

        # 🔹 Base visibility rules
        if user.groups.filter(name="Requisitioner").exists():
            queryset = queryset.filter(created_by=user).exclude(unassigned_q)
        elif not user.groups.filter(name__in=["Procurement", "Admin"]).exists():
            return PurchaseRequest.objects.none()

        # 🔹 Filters from GET parameters
        assigned_filter = self.request.GET.get("assigned")
        office_filter = self.request.GET.get("office")
        pr_number_search = self.request.GET.get("pr_number")

        # 🧩 Procurement/Admin: Can use all filters
        if user.groups.filter(name__in=["Procurement", "Admin"]).exists():
            if assigned_filter == "unassigned":
                queryset = queryset.filter(unassigned_q)
            elif assigned_filter == "assigned":
                queryset = queryset.exclude(unassigned_q)

            if office_filter:
                queryset = queryset.filter(office_section__icontains=office_filter)

        # 🧩 All users: Can search by PR number
        if pr_number_search:
            queryset = queryset.filter(pr_number__icontains=pr_number_search)

        return queryset.order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        is_procurement = user.groups.filter(name__in=["Procurement", "Admin"]).exists()

        # Preserve filter values
        context["assigned_filter"] = self.request.GET.get("assigned", "")
        context["office_filter"] = self.request.GET.get("office", "")
        context["pr_number_search"] = self.request.GET.get("pr_number", "")
        context["is_procurement"] = is_procurement

        # 🧩 Show office list only for Procurement/Admin
        if is_procurement:
            context["offices"] = (
                PurchaseRequest.objects.values_list("office_section", flat=True)
                .distinct()
                .order_by("office_section")
            )

        return context



# -----------------------
# CREATE PURCHASE REQUEST (REQUISITIONER)
# -----------------------
class PRCreateView(LoginRequiredMixin, generic.CreateView):
    model = PurchaseRequest
    form_class = RequisitionerPRForm
    template_name = "procurement/pr_form.html"

    def get(self, request):
        form = self.form_class()  # ✅ instantiate
        formset = PRItemFormSet(prefix="form")
        return render(request, self.template_name, {
            "form": form,
            "formset": formset,
            "is_procurement": False,
        })

    def post(self, request):
        form = self.form_class(request.POST, request.FILES)  # ✅ instantiate properly
        formset = PRItemFormSet(request.POST, prefix="form")

        if form.is_valid() and formset.is_valid():  # ✅ works now
            pr = form.save(commit=False)
            pr.created_by = request.user
            pr.save()

            formset.instance = pr
            formset.save()

            messages.success(request, "Purchase Request created successfully.")
            return redirect("procurement:pr_detail", pk=pr.pk)

        messages.error(request, "Please correct the errors below.")
        return render(request, self.template_name, {
            "form": form,
            "formset": formset,
            "is_procurement": False,
        })




# -----------------------
# PROCUREMENT WORKFLOW VIEW
# -----------------------
class PRWorkflowView(LoginRequiredMixin, View):
    template_name = "procurement/pr_workflow.html"

    def get_object(self, pk=None):
        if pk:
            return get_object_or_404(PurchaseRequest, pk=pk)
        return None

    def get(self, request, pk):
        pr = self.get_object(pk)
        form = ProcurementStaffPRForm
        formset = PRItemFormSet(instance=pr, prefix="form")
        is_procurement = request.user.groups.filter(name="Procurement").exists()
        return render(request, self.template_name, {
            "form": form,
            "formset": formset,
            "pr": pr,
            "is_procurement": is_procurement,
        })

    def post(self, request, pk):
        pr = self.get_object(pk)
        form = ProcurementStaffPRForm(request.POST, instance=pr)
        formset = PRItemFormSet(request.POST, instance=pr, prefix="form")

        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "Purchase Request updated successfully.")
            return redirect("procurement:pr_detail", pk=pr.pk)

        messages.error(request, "Please correct the errors below.")
        is_procurement = request.user.groups.filter(name="Procurement").exists()
        return render(request, self.template_name, {
            "form": form,
            "formset": formset,
            "pr": pr,
            "is_procurement": is_procurement,
        })

# -----------------------
# ASSIGN PR NUMBER
# -----------------------
@login_required
@user_passes_test(in_procurement_group)
def assign_pr_number(request, pk):
    pr = get_object_or_404(PurchaseRequest, pk=pk)

    if request.method == "POST":
        form = AssignPRNumberForm(request.POST, instance=pr)
        if form.is_valid():
            form.save()
            messages.success(request, f"PR {pr.pr_number} assigned successfully.")
            return redirect("procurement:pr_detail", pk=pr.pk)
    else:
        form = AssignPRNumberForm(instance=pr)

    grand_total = sum(
        (item.quantity or 0) * (item.unit_cost or 0)
        for item in pr.items.all()
    )

    return render(
        request,
        "procurement/assign_pr_number.html",
        {
            "form": form,
            "pr": pr,
            "grand_total": grand_total,
        }
    )

# -----------------------
# SUPPLIERS
# -----------------------
class SupplierListView(LoginRequiredMixin, generic.ListView):
    model = Supplier
    template_name = "procurement/supplier_list.html"
    context_object_name = "suppliers"


class SupplierCreateView(LoginRequiredMixin, generic.CreateView):
    model = Supplier
    form_class = SupplierForm
    template_name = "procurement/supplier_form.html"
    success_url = reverse_lazy("procurement:supplier_list")


# -----------------------
# RFQ / APR
# -----------------------
@login_required
def create_rfq(request, pr_id):
    pr = get_object_or_404(PurchaseRequest, id=pr_id)
    if request.method == "POST":
        form = RFQForm(request.POST)
        if form.is_valid():
            rfq = form.save(commit=False)
            rfq.purchase_request = pr
            rfq.created_by = request.user
            rfq.save()
            rfq.consolidated_prs.add(pr)
            pr.consolidated_in = rfq
            pr.save(update_fields=["consolidated_in"])
            messages.success(request, "RFQ created successfully.")
            return redirect("procurement:rfq_preview", pk=rfq.pk)
    else:
        form = RFQForm()
    return render(request, "procurement/create_rfq.html", {"form": form, "pr": pr})

@login_required
def create_apr(request, pr_id):
    pr = get_object_or_404(PurchaseRequest, id=pr_id)
    if request.method == "POST":
        form = APRForm(request.POST)
        if form.is_valid():
            apr = form.save(commit=False)
            apr.purchase_request = pr
            apr.created_by = request.user
            apr.save()
            messages.success(request, "APR created successfully.")
            return redirect("procurement:pr_detail", pk=pr.pk)
    else:
        form = APRForm()
    return render(request, "procurement/create_apr.html", {"form": form, "pr": pr})


# -----------------------
# AOQ / PO
# -----------------------
@login_required
def create_aoq(request, rfq_id):
    rfq = get_object_or_404(RequestForQuotation, id=rfq_id)
    aoq, created = AbstractOfQuotation.objects.get_or_create(rfq=rfq)
    if request.method == "POST":
        formset = AOQLineFormSet(request.POST, instance=aoq)
        if formset.is_valid():
            formset.save()
            messages.success(request, "AOQ lines saved.")
            return redirect("procurement:aoq_detail", pk=aoq.pk)
    else:
        formset = AOQLineFormSet(instance=aoq)
    return render(request, "procurement/create_aoq.html", {"formset": formset, "rfq": rfq, "aoq": aoq})


class AOQDetailView(LoginRequiredMixin, generic.DetailView):
    model = AbstractOfQuotation
    template_name = "procurement/aoq_detail.html"
    context_object_name = "aoq"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        aoq = self.object  # ✅ FIX — get the AOQ instance
        pr = aoq.rfq.purchase_request

        # Supplier summaries
        context["supplier_summary"] = aoq.supplier_summary()

        # Winner + savings
        winner, winning_total, pr_total, savings, pct = aoq.winning_supplier_and_savings()
        context.update({
            "winner_supplier": winner,
            "winning_total": winning_total,
            "pr_total": pr_total,
            "savings": savings,
            "pct_savings": pct,
        })

        # PR breakdown by category
        context["pr_breakdown"] = pr.breakdown_by_budget()

        # AOQ breakdown by category (safe)
        def category_breakdown(aoq_obj):
            breakdown = {}
            for line in aoq_obj.lines.select_related("pr_item"):
                category = line.pr_item.budget_category
                total = (line.unit_price or 0) * (line.pr_item.quantity or 0)
                breakdown[category] = breakdown.get(category, 0) + total
            return breakdown

        context["aoq_breakdown_by_category"] = category_breakdown(aoq)  # ✅ aoq now defined

        return context

class AOQListView(LoginRequiredMixin, generic.ListView):
    model = AbstractOfQuotation
    template_name = "procurement/aoq_list.html"
    context_object_name = "aoqs"
    ordering = ["-created_at"]


def find_lcrb_for_item(aoq, pr_item):
    lines = aoq.lines.filter(pr_item=pr_item, responsive=True).order_by("unit_price")
    return lines.first()


@login_required
def generate_po_from_aoq(request, pk):
    aoq = get_object_or_404(AbstractOfQuotation, pk=pk)
    supplier_wins = {}
    for line in aoq.lines.filter(responsive=True):
        winner_line = find_lcrb_for_item(aoq, line.pr_item)
        if winner_line:
            supplier_wins.setdefault(winner_line.supplier.id, 0)
            supplier_wins[winner_line.supplier.id] += 1
    if not supplier_wins:
        messages.error(request, "No responsive bids found.")
        return redirect("procurement:aoq_detail", pk=aoq.pk)

    best_supplier_id = max(supplier_wins, key=supplier_wins.get)
    supplier = Supplier.objects.get(id=best_supplier_id)
    po = PurchaseOrder.objects.create(
        aoq=aoq, supplier=supplier,
        created_by=request.user,
        submission_date=timezone.now().date(),
        receiving_office="To be set"
    )
    po.po_number = f"PO-{timezone.now().strftime('%Y%m%d')}-{po.id}"
    po.save()
    messages.success(request, f"Purchase Order {po.po_number} created for {supplier.name}")
    return redirect("procurement:po_detail", pk=po.pk)


class PODetailView(LoginRequiredMixin, generic.DetailView):
    model = PurchaseOrder
    template_name = "procurement/po_detail.html"
    context_object_name = "po"

class POListView(LoginRequiredMixin, generic.ListView):
    model = PurchaseOrder
    template_name = "procurement/po_list.html"
    context_object_name = "pos"
    ordering = ["-created_at"]

# -----------------------
# LOGIN VIEW
# -----------------------
class EVSULoginView(LoginView):
    template_name = "registration/login.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("procurement:dashboard")
        return super().dispatch(request, *args, **kwargs)

# -----------------------
# RFQ LIST & PREVIEW
# -----------------------
class RFQListView(LoginRequiredMixin, generic.ListView):
    model = RequestForQuotation
    template_name = "procurement/rfq_list.html"
    context_object_name = "rfqs"
    ordering = ["-id"]

class RFQPreviewView(LoginRequiredMixin, generic.DetailView):
    model = RequestForQuotation
    template_name = "procurement/rfq_preview.html"
    context_object_name = "rfq"

class PRDetailView(LoginRequiredMixin, generic.DetailView):
    model = PurchaseRequest
    template_name = "procurement/pr_detail.html"
    context_object_name = "pr"

    def get_queryset(self):
        user = self.request.user

        # 🧩 Requisitioners can only access their own PRs
        if user.groups.filter(name="Requisitioner").exists():
            return PurchaseRequest.objects.filter(created_by=user)

        # 🧩 Procurement & Admins can access all
        return PurchaseRequest.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pr = self.object
        grand_total = sum(
            (item.quantity or 0) * (item.unit_cost or 0)
            for item in pr.items.all()
        )
        context["grand_total"] = grand_total
        return context



# Update View

class PRUpdateView(LoginRequiredMixin, generic.UpdateView):
    model = PurchaseRequest
    form_class = RequisitionerPRForm
    template_name = "procurement/pr_form.html"

    def get(self, request, *args, **kwargs):
        pr = self.get_object()
        form = self.form_class(instance=pr)
        formset = PRItemFormSet(instance=pr, prefix="form")
        return render(request, self.template_name, {
            "form": form,
            "formset": formset,
            "edit_mode": True,
            "pr": pr
        })

    def post(self, request, *args, **kwargs):
        pr = self.get_object()

        # ✅ FIXED: include request.FILES
        form = self.form_class(request.POST, request.FILES, instance=pr)
        formset = PRItemFormSet(request.POST, request.FILES, instance=pr, prefix="form")

        print("---- FORM ERRORS ----")
        print(form.errors)
        print("---- FORMSET ERRORS ----")
        print(formset.errors)

        if form.is_valid() and formset.is_valid():
            pr = form.save(commit=False)
            pr.last_update = timezone.now()
            pr.save()
            formset.instance = pr
            formset.save()

            messages.success(request, f"Purchase Request {pr.pr_number or pr.id} updated successfully.")
            return redirect("procurement:pr_detail", pk=pr.pk)

        # If validation fails
        messages.error(request, "Please correct the errors below.")
        return render(request, self.template_name, {
            "form": form,
            "formset": formset,
            "edit_mode": True,
            "pr": pr
        })

    def dispatch(self, request, *args, **kwargs):
        pr = self.get_object()
        if request.user.groups.filter(name="Requisitioner").exists() and pr.created_by != request.user:
            messages.error(request, "You are not authorized to edit this purchase request.")
            return redirect("procurement:dashboard")
        return super().dispatch(request, *args, **kwargs)
    


@login_required
def pr_preview(request, pk):
    pr = get_object_or_404(PurchaseRequest, pk=pk)
    auto_print = request.GET.get("auto_print") == "true"
    total_amount = sum(item.quantity * item.unit_cost for item in pr.items.all())
    return render(request, "procurement/pr_preview.html", {
        "pr": pr,
        "total_amount": total_amount,
        "auto_print": auto_print,
    })


@login_required
def submit_pr_for_verification(request, pk):
    pr = get_object_or_404(PurchaseRequest, pk=pk)

    # Only allow Requisitioners to submit
    if not request.user.groups.filter(name="Requisitioner").exists():
        messages.error(request, "You are not authorized to submit this request.")
        return redirect("procurement:pr_detail", pk=pk)

    # Only submit if still in draft
    if pr.status != "draft":
        messages.warning(request, "This request has already been submitted.")
        return redirect("procurement:pr_detail", pk=pk)
    
        # ✅ Only the owner can submit their own PR
    if request.user != pr.created_by:
        messages.error(request, "You can only submit your own purchase requests.")
        return redirect("procurement:dashboard")

    # Update status
    pr.status = "submitted"
    pr.save()
    messages.success(request, f"Purchase Request {pr.pr_number or pr.id} has been submitted for verification.")
    return redirect("procurement:pr_detail", pk=pk)



@login_required
def pr_preview(request, pk):
    """Print-friendly view of the Purchase Request."""
    pr = get_object_or_404(PurchaseRequest, pk=pk)
    return render(request, "procurement/pr_preview.html", {"pr": pr, "auto_print": True})


class UnassignedPRListView(LoginRequiredMixin, ListView):
    model = PurchaseRequest
    template_name = 'procurement/unassigned_pr_list.html'
    context_object_name = 'prs'

    def get_queryset(self):
        user = self.request.user

        # Base filter for unassigned PRs (handles NULL, empty string, and 'Unassigned')
        unassigned_q = Q(pr_number__isnull=True) | Q(pr_number__exact='') | Q(pr_number__iexact='Unassigned')

        # 🧩 Requisitioners → only their own unassigned PRs
        if user.groups.filter(name="Requisitioner").exists():
            return (
                PurchaseRequest.objects
                .filter(unassigned_q, created_by=user)
                .order_by('-created_at')
            )

        # 🧩 Procurement/Admin → all unassigned PRs
        if user.groups.filter(name__in=["Procurement", "Admin"]).exists():
            return (
                PurchaseRequest.objects
                .filter(unassigned_q)
                .order_by('-created_at')
            )

        # 🧩 Default → none
        return PurchaseRequest.objects.none()


@login_required
@user_passes_test(in_procurement_group)
@csrf_exempt
def update_mode_ajax(request, pk):
    """AJAX endpoint to update Mode of Procurement dynamically."""
    try:
        pr = PurchaseRequest.objects.get(pk=pk)
    except PurchaseRequest.DoesNotExist:
        return JsonResponse({"success": False, "error": "PR not found"}, status=404)

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            mode = data.get("mode_of_procurement", "").strip()
            subtype = data.get("negotiated_type", "").strip()

            pr.mode_of_procurement = mode or None
            pr.negotiated_type = subtype or None
            pr.save(update_fields=["mode_of_procurement", "negotiated_type"])

            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=400)

    return JsonResponse({"success": False, "error": "Invalid request"}, status=400)


# Helper to compute allowed statuses server-side (same mapping as JS)
def _allowed_statuses_for_mode(mode):
    DEFAULT = ['draft','submitted','verified','endorsed','approved']
    RFQ_FLOW = ['for_mop','for_rfq','for_award','for_po','po_issued','delivered','inspected','closed']
    PB_FLOW = ['for_pb','pre_bid','bidding_open','bid_evaluation','post_qualification','bac_resolution','notice_of_award','contract_preparation','contract_signed','notice_to_proceed','delivery_completed','payment_processing','cancelled','failed_bidding','disqualified']

    RFQ_FLOW_MODES = set([
        'Direct Contracting','Direct Acquisition','Repeat Order','Small Value Procurement',
        'Negotiated Procurement','Direct Sales','Direct Procurement for Science, Technology and Innovation'
    ])
    PB_FLOW_MODES = set([
        'Competitive Bidding','Limited Source Bidding','Competitive Dialogue','Unsolicited Offer with Bid Matching'
    ])

    if mode in RFQ_FLOW_MODES:
        return RFQ_FLOW
    if mode in PB_FLOW_MODES:
        return PB_FLOW
    return DEFAULT

@login_required
@csrf_exempt  # we rely on X-CSRFToken header; you may remove csrf_exempt if you use standard CSRF middleware and cookie header
def update_status_ajax(request, pk):
    """
    JSON POST: { "status": "<new_status>" }
    Permissions:
      - Procurement (and Admin) can update status.
      - Requisitioner cannot modify status (read-only).
    Server-side validates allowed statuses for the PR's mode before saving.
    """
    try:
        pr = PurchaseRequest.objects.get(pk=pk)
    except PurchaseRequest.DoesNotExist:
        return JsonResponse({"success": False, "error": "PR not found"}, status=404)

    # RBAC: only procurement/admin can change status
    if not (request.user.groups.filter(name='Procurement').exists() or request.user.is_superuser or request.user.groups.filter(name='Admin').exists()):
        return JsonResponse({"success": False, "error": "Permission denied"}, status=403)

    if request.method != 'POST':
        return JsonResponse({"success": False, "error": "Invalid request method (POST required)"}, status=400)

    try:
        payload = json.loads(request.body or '{}')
        new_status = (payload.get('status') or '').strip()
    except Exception as e:
        return JsonResponse({"success": False, "error": "Invalid JSON payload"}, status=400)

    if not new_status:
        return JsonResponse({"success": False, "error": "Status value required"}, status=400)

    allowed = _allowed_statuses_for_mode(pr.mode_of_procurement or '')

    if new_status not in allowed:
        return JsonResponse({"success": False, "error": "Status not allowed for the current Mode of Procurement"}, status=400)

    # Optionally map status codes to readable labels or set pr.status to new_status directly
    pr.status = new_status
    pr.last_update = timezone.now()
    pr.save(update_fields=['status','last_update'])

    # Return success and formatted last_update
    return JsonResponse({
        "success": True,
        "last_update": pr.last_update.strftime("%b %d, %Y %H:%M"),
    })

# Reusable permission mixin
class ProcurementOrAdminMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.groups.filter(name__in=["Procurement", "Admin"]).exists()

# List
class SignatoryListView(LoginRequiredMixin, ListView):
    model = Signatory
    template_name = "procurement/signatory_list.html"
    context_object_name = "signatories"


# Create (regular page)
@method_decorator(login_required, name="dispatch")
class SignatoryCreateView(ProcurementOrAdminMixin, CreateView):
    model = Signatory
    fields = ["name", "designation"]
    template_name = "procurement/signatory_form.html"
    success_url = reverse_lazy("procurement:signatory_list")

# Update (regular page)
@method_decorator(login_required, name="dispatch")
class SignatoryUpdateView(ProcurementOrAdminMixin, UpdateView):
    model = Signatory
    fields = ["name", "designation"]
    template_name = "procurement/signatory_form.html"
    success_url = reverse_lazy("procurement:signatory_list")

# Delete (regular page)
@method_decorator(login_required, name="dispatch")
class SignatoryDeleteView(ProcurementOrAdminMixin, DeleteView):
    model = Signatory
    template_name = "procurement/signatory_confirm_delete.html"
    success_url = reverse_lazy("procurement:signatory_list")

# ---------- AJAX Handlers ----------
@login_required
@require_POST
def signatory_add_ajax(request):
    # Accept form-encoded (POST) or JSON
    try:
        if request.content_type == "application/json":
            data = json.loads(request.body.decode())
            name = data.get("name", "").strip()
            designation = data.get("designation", "").strip()
        else:
            name = request.POST.get("name", "").strip()
            designation = request.POST.get("designation", "").strip()

        if not name or not designation:
            return JsonResponse({"success": False, "error": "Missing required fields"}, status=400)

        if not request.user.groups.filter(name__in=["Procurement", "Admin"]).exists():
            return HttpResponseForbidden("Insufficient permissions")

        s = Signatory.objects.create(name=name, designation=designation)
        return JsonResponse({"success": True, "id": s.pk, "name": s.name, "designation": s.designation})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)

@login_required
@require_POST
def signatory_edit_ajax(request, pk):
    try:
        if request.content_type == "application/json":
            data = json.loads(request.body.decode())
            name = data.get("name", "").strip()
            designation = data.get("designation", "").strip()
        else:
            name = request.POST.get("name", "").strip()
            designation = request.POST.get("designation", "").strip()

        if not name or not designation:
            return JsonResponse({"success": False, "error": "Missing required fields"}, status=400)

        if not request.user.groups.filter(name__in=["Procurement", "Admin"]).exists():
            return HttpResponseForbidden("Insufficient permissions")

        signatory = get_object_or_404(Signatory, pk=pk)
        signatory.name = name
        signatory.designation = designation
        signatory.save()
        return JsonResponse({"success": True})
    except Signatory.DoesNotExist:
        return JsonResponse({"success": False, "error": "Not found"}, status=404)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)

@login_required
@require_POST
def signatory_delete_ajax(request, pk):
    try:
        if not request.user.groups.filter(name__in=["Procurement", "Admin"]).exists():
            return HttpResponseForbidden("Insufficient permissions")

        signatory = get_object_or_404(Signatory, pk=pk)
        signatory.delete()
        return JsonResponse({"success": True})
    except Signatory.DoesNotExist:
        return JsonResponse({"success": False, "error": "Not found"}, status=404)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)
    
@login_required
@user_passes_test(in_procurement_group)
def rfq_process(request, pk):
    """
    RFQ overview page: shows RFQ details and list of bidders.
    """
    rfq = get_object_or_404(RequestForQuotation, pk=pk)
    bids = rfq.bids.select_related("supplier").all()
    return render(request, "procurement/rfq_process.html", {"rfq": rfq, "bids": bids})


@login_required
@user_passes_test(in_procurement_group)
def add_bid(request, rfq_id):
    rfq = get_object_or_404(RequestForQuotation, pk=rfq_id)
    if request.method == "POST":
        form = BidForm(request.POST, rfq=rfq)
        if form.is_valid():
            bid = form.save(commit=False)
            bid.rfq = rfq
            bid.created_by = request.user
            bid.save()
            messages.success(request, "Bidder added successfully.")
            return redirect("procurement:rfq_process", pk=rfq.pk)
    else:
        form = BidForm(rfq=rfq)
    return render(request, "procurement/add_bid.html", {"form": form, "rfq": rfq})


@login_required
@user_passes_test(in_procurement_group)
def edit_bid(request, bid_id):
    bid = get_object_or_404(Bid, pk=bid_id)
    rfq = bid.rfq
    if request.method == "POST":
        form = BidForm(request.POST, instance=bid, rfq=rfq)
        if form.is_valid():
            form.save()
            messages.success(request, "Bid updated successfully.")
            return redirect("procurement:rfq_process", pk=rfq.pk)
    else:
        form = BidForm(instance=bid, rfq=rfq)
    return render(request, "procurement/edit_bid.html", {"form": form, "bid": bid, "rfq": rfq})


@login_required
@user_passes_test(in_procurement_group)
@require_POST
def remove_bid(request, bid_id):
    bid = get_object_or_404(Bid, pk=bid_id)
    rfq_pk = bid.rfq.pk
    bid.delete()
    messages.success(request, "Bidder removed.")
    return redirect("procurement:rfq_process", pk=rfq_pk)


@login_required
@user_passes_test(in_procurement_group)
def enter_bid_lines(request, bid_id):
    """
    Enter per-item prices for a Bid. Enforces that all PRItems in the RFQ's PR
    have a corresponding BidLine (i.e., completeness) before final save.
    """
    bid = get_object_or_404(Bid, pk=bid_id)
    rfq = bid.rfq
    pr = rfq.purchase_request
    pr_items = list(rfq_pr_items(rfq))

    if request.method == "POST":
        formset = BidLineFormSet(request.POST, instance=bid)

        if formset.is_valid():
            # Save in memory (not committed yet) so we can validate completeness
            lines = formset.save(commit=False)

            # Build set of PRItem IDs provided in the formset (including existing ones)
            provided_pr_item_ids = set()
            for line in lines:
                if line.pr_item_id:
                    provided_pr_item_ids.add(line.pr_item_id)

            # Also include the formset's deleted/unchanged existing lines (if not deleted)
            # Note: formset.deleted_forms list contains forms marked for deletion.
            existing_lines_qs = BidLine.objects.filter(bid=bid)
            for existing in existing_lines_qs:
                # Check whether this existing line was removed in formset:
                # If the existing.pk is in any form.cleaned_data pk marked for delete, skip
                # We will rely on provided_pr_item_ids + final save to reflect final state.
                provided_pr_item_ids.add(existing.pr_item_id)

            # Determine which PRItems are missing
            missing = [itm for itm in pr_items if itm.pk not in provided_pr_item_ids]

            if missing:
                # Formset is valid but incomplete: refuse to accept and display message
                names = ", ".join([str(m.description) for m in missing])
                messages.error(request,
                    "Bid lines are incomplete. Please provide prices for all PR items: "
                    f"{names}"
                )
                # Re-render formset (without saving any changes)
                return render(request, "procurement/enter_bid_lines.html", {
                    "bid": bid, "formset": formset, "rfq": rfq, "pr_items": pr_items
                })

            # Everything is present — save changes
            # Delete objects marked for deletion
            for obj in formset.deleted_objects:
                obj.delete()

            # Save/attach new or changed lines
            for line in lines:
                line.bid = bid
                line.save()

            # Optionally update bid status to 'submitted' (if you use that)
            if bid.status != "submitted":
                bid.status = "submitted"
                bid.save(update_fields=['status'])

            messages.success(request, "Bid lines saved successfully and are complete.")
            return redirect("procurement:rfq_process", pk=rfq.pk)

        # invalid formset
        messages.error(request, "Please correct the errors in the form.")
        return render(request, "procurement/enter_bid_lines.html", {
            "bid": bid, "formset": formset, "rfq": rfq, "pr_items": pr_items
        })

    else:

        formset = BidLineFormSet(instance=bid)

        # Ensure all PR items have a BidLine entry (auto-create missing ones)
        existing_pr_item_ids = set(bid.lines.values_list("pr_item_id", flat=True))
        for pr_item in pr_items:
            if pr_item.id not in existing_pr_item_ids:
                BidLine.objects.create(
                    bid=bid,
                    pr_item=pr_item,
                    unit_price=0,
                    compliant=True,
                )

        # Reload the formset after ensuring all lines exist
        formset = BidLineFormSet(instance=bid)

        return render(request, "procurement/enter_bid_lines.html", {
            "bid": bid,
            "formset": formset,
            "rfq": rfq,
            "pr_items": pr_items,
        })


@login_required
@user_passes_test(in_procurement_group)
def create_aoq_from_rfq(request, rfq_id):
    rfq = get_object_or_404(RequestForQuotation, pk=rfq_id)
    aoq, created = AbstractOfQuotation.objects.get_or_create(rfq=rfq)
    if created:
        messages.success(request, "AOQ created.")
    else:
        messages.info(request, "AOQ already exists.")
    return redirect("procurement:aoq_detail", pk=aoq.pk)


def abstract_of_quotation(request, rfq_id):
    rfq = get_object_or_404(RequestForQuotation, pk=rfq_id)
    pr = rfq.purchase_request
    items = rfq_pr_items(rfq)
    bids = rfq.bids.select_related("supplier").prefetch_related("lines__pr_item")

    # Prepare a mapping of supplier → {pr_item_id → BidLine}
    supplier_data = {}
    for bid in bids:
        supplier_data[bid.supplier] = {}
        for line in bid.lines.all():
            supplier_data[bid.supplier][line.pr_item_id] = line

    context = {
        "rfq": rfq,
        "items": items,
        "suppliers": [bid.supplier for bid in bids],
        "supplier_data": supplier_data,
    }
    return render(request, "procurement/aoq_summary.html", context)


@login_required
@user_passes_test(in_procurement_group)
@require_POST
def award_aoq(request, aoq_id):
    aoq = get_object_or_404(AbstractOfQuotation, pk=aoq_id)
    supplier_id = request.POST.get('supplier_id')
    if not supplier_id:
        messages.error(request, "Supplier selection required.")
        return redirect("procurement:aoq_detail", pk=aoq.pk)

    try:
        po = aoq.award(supplier_id, awarded_by=request.user)
        messages.success(request, f"Awarded and PO {po.po_number} created.")
        return redirect("procurement:po_detail", pk=po.pk)
    except Exception as e:
        messages.error(request, f"Award failed: {str(e)}")
        return redirect("procurement:aoq_detail", pk=aoq.pk)

@login_required
@user_passes_test(in_procurement_group)
@require_POST
def advance_pr_stage(request, pr_id):
    pr = get_object_or_404(PurchaseRequest, pk=pr_id)
    action = request.POST.get('action')
    transitions = {
        "to_rfq": "for_rfq",
        "to_award": "for_award",
        "to_po": "for_po",
    }

    if action not in transitions:
        messages.error(request, "Unknown transition.")
        return redirect("procurement:pr_detail", pk=pr.pk)

    new_status = transitions[action]

    # server-side prereq validation happens in step 7
    ok, err = validate_pr_transition(pr, new_status)
    if not ok:
        messages.error(request, f"Cannot transition: {err}")
        return redirect("procurement:pr_detail", pk=pr.pk)

    pr.status = new_status
    pr.last_update = timezone.now()
    pr.save(update_fields=["status", "last_update"])
    messages.success(request, f"PR moved to {pr.get_status_display()}.")
    return redirect("procurement:pr_detail", pk=pr.pk)

def validate_pr_transition(pr, new_status):
    """
    Returns (True, None) if allowed, else (False, "reason string").
    """
    # move to RFQ: PR must have items and pr_number assigned
    if new_status == "for_rfq":
        if pr.items.count() == 0:
            return False, "PR has no items."
        if not pr.pr_number:
            return False, "PR number must be assigned first."
        return True, None

    # move to AWARD: AOQ should exist and contain responsive lines
    if new_status == "for_award":
        rfq = getattr(pr, "rfq", None)
        if not rfq:
            return False, "RFQ not created for this PR."
        aoq = getattr(rfq, "aoq", None)
        if not aoq:
            return False, "AOQ must be created before moving to award."
        # ensure at least one responsive line exists
        if not aoq.lines.filter(responsive=True).exists():
            return False, "No responsive AOQ lines found."
        return True, None

    # move to PO: AOQ must be awarded (awarded_to set)
    if new_status == "for_po":
        rfq = getattr(pr, "rfq", None)
        aoq = getattr(rfq, "aoq", None) if rfq else None
        if not aoq or not getattr(aoq, "awarded_to", None):
            return False, "AOQ must be awarded before creating PO."
        return True, None

    return True, None

@login_required
@user_passes_test(in_procurement_group)
@require_POST
def award_aoq_view(request, aoq_id):
    aoq = get_object_or_404(AbstractOfQuotation, pk=aoq_id)
    supplier_id = request.POST.get("supplier_id")
    try:
        po = award_aoq_and_create_po(aoq, supplier_id, awarded_by=request.user)
        messages.success(request, f"Awarded. PO {po.po_number} created.")
        return redirect("procurement:po_detail", pk=po.pk)
    except Exception as e:
        messages.error(request, f"Award failed: {e}")
        return redirect("procurement:aoq_detail", pk=aoq.pk)
    

@login_required
@user_passes_test(in_procurement_group)
@require_POST
def save_resolution(request, rfq_id):
    rfq = get_object_or_404(RequestForQuotation, pk=rfq_id)
    resolution_text = request.POST.get("resolution", "").strip()
    rfq.resolution = resolution_text
    rfq.resolution_by = request.user
    rfq.resolution_at = timezone.now()
    rfq.save(update_fields=["resolution","resolution_by","resolution_at"])
    messages.success(request, "Resolution saved.")
    return redirect("procurement:rfq_process", pk=rfq.pk)

@login_required
@user_passes_test(in_procurement_group)
def aoq_export_csv(request, aoq_id):
    aoq = get_object_or_404(AbstractOfQuotation, pk=aoq_id)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="aoq_{aoq.pk}_summary.csv"'
    writer = csv.writer(response)
    writer.writerow(["Supplier", "Total", "Responsive Lines"])
    for s in aoq.supplier_summary():
        writer.writerow([s['supplier'].name, f"{s['total']:.2f}", s['responsive_count']])
    return response

@login_required
@user_passes_test(in_procurement_group)
@require_POST
def consolidate_to_rfq(request):
    """
    Create a consolidated RFQ from multiple PRs (selected_prs comes as CSV of ids).
    - RFQ number is based on the first selected PR number.
    - Selected PRs are linked to the created RFQ.
    - Each PR.consolidated_in is updated.
    - Consolidation is logged.
    """
    selected = request.POST.get("selected_prs", "")
    remarks = request.POST.get("remarks", "") or ""

    if not selected:
        messages.error(request, "Please select at least one Purchase Request to consolidate.")
        return redirect("procurement:pr_list")

    ids = [int(x) for x in selected.split(",") if x.strip().isdigit()]
    prs = PurchaseRequest.objects.filter(id__in=ids)

    if not prs.exists():
        messages.error(request, "No valid Purchase Requests found.")
        return redirect("procurement:pr_list")

    # ✅ Use the first PR as the reference for RFQ number
    first_pr = prs.first()
    rfq_number = f"RFQ-{first_pr.pr_number}"

    # ✅ Prevent duplicate RFQ numbers
    if RequestForQuotation.objects.filter(rfq_number=rfq_number).exists():
        messages.error(request, f"RFQ for {first_pr.pr_number} already exists.")
        return redirect("procurement:pr_list")

    # ✅ Create the RFQ
    rfq = RequestForQuotation.objects.create(
        rfq_number=rfq_number,
        created_by=request.user,
        remarks=remarks,
    )

    # ✅ Link PRs to the RFQ
    rfq.consolidated_prs.set(prs)
    rfq.save()

    for pr in prs:
        pr.consolidated_in = rfq
        pr.save(update_fields=["consolidated_in"])

    # ✅ Optional: Log the consolidation if the model exists
    try:
        log = RFQConsolidationLog.objects.create(
            rfq=rfq,
            consolidated_by=request.user,
            remarks=remarks,
        )
        log.consolidated_prs.set(prs)
    except NameError:
        # Skip logging if model not defined
        pass

    messages.success(request, f"RFQ {rfq.rfq_number} created from {prs.count()} PR(s).")
    return redirect("procurement:rfq_process", pk=rfq.pk)


@login_required
def rfq_detail(request, pk):
    rfq = get_object_or_404(RequestForQuotation, pk=pk)
    return render(request, "procurement/rfq_detail.html", {"rfq": rfq})

@login_required
def pr_list(request):
    pr_queryset = PurchaseRequest.objects.all()

    # Detect if PR is part of any RFQ (either one-to-one or many-to-one)
    rfq_exists_subquery = RequestForQuotation.objects.filter(
        consolidated_prs=OuterRef('pk')
    )

    pr_queryset = pr_queryset.annotate(
        has_rfq=Exists(RequestForQuotation.objects.filter(purchase_request=OuterRef('pk'))),
        in_consolidated_rfq=Exists(rfq_exists_subquery)
    )

    context = {
        'pr_list': pr_queryset,
    }
    return render(request, 'procurement/pr_list.html', context)

def print_pr(request, pk):
    pr = get_object_or_404(PurchaseRequest, pk=pk)

    # Select the officer info dynamically
    if pr.funding == "TRF":
        officer_name = "RUBY N. MANCIO, CPA"
        officer_title = "University Accountant"
    else:
        officer_name = "EVONE MAE KARMELLE P. BARANDA, CPA"
        officer_title = "OIC, Head Budget Office"

    html_string = render_to_string("procurement/pr_preview.html", {
        "pr": pr,
        "officer_name": officer_name,
        "officer_title": officer_title,
    })
    pdf = HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()
    return HttpResponse(pdf, content_type="application/pdf")
