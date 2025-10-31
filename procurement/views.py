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
from django.db.models import Q
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST
from .models import Signatory

from .models import (
    PurchaseRequest, PRItem, Supplier,
    RequestForQuotation, AgencyProcurementRequest,
    AbstractOfQuotation, AOQLine, PurchaseOrder
)
from .forms import (
    RequisitionerPRForm, ProcurementStaffPRForm,
    PRItemFormSet, SupplierForm,
    RFQForm, APRForm, AOQLineFormSet, PurchaseOrderForm,
    AssignPRNumberForm
)


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
from django.db.models import Q

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

    return render(request, "procurement/assign_pr_number.html", {"form": form, "pr": pr})


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


from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json

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

from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
from django.contrib.auth.decorators import login_required, user_passes_test

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