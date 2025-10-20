from django.shortcuts import render, redirect, get_object_or_404
from django.views import generic, View
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils import timezone
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.views.generic import DetailView
from django.views.generic import UpdateView

from .models import (
    PurchaseRequest, PRItem, Supplier,
    RequestForQuotation, AgencyProcurementRequest,
    AbstractOfQuotation, AOQLine, PurchaseOrder
)
from .forms import (
    PurchaseRequestForm, PRItemFormSet, SupplierForm,
    RFQForm, APRForm, AOQLineFormSet, PurchaseOrderForm,
    ProcurementPRForm, AssignPRNumberForm
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
        context["user"] = user
        context["pr_count"] = PurchaseRequest.objects.filter(created_by=user).count()
        context["rfq_count"] = RequestForQuotation.objects.count()
        context["aoq_count"] = AbstractOfQuotation.objects.count()
        context["po_count"] = PurchaseOrder.objects.count()


        if user.groups.filter(name="Procurement").exists():
            context["welcome_text"] = "Procurement Officer Dashboard"
        elif user.groups.filter(name="Requisitioner").exists():
            context["welcome_text"] = "Requisitioner Dashboard"
        elif user.groups.filter(name="Admin").exists():
            context["welcome_text"] = "Admin Dashboard"
        else:
            context["welcome_text"] = "User Dashboard"

        return context

# -----------------------
# PURCHASE REQUEST VIEWS
# -----------------------
class PRListView(LoginRequiredMixin, generic.ListView):
    model = PurchaseRequest
    template_name = "procurement/pr_list.html"
    context_object_name = "prs"
    ordering = ["-created_at"]

# -----------------------
# CREATE PURCHASE REQUEST (REQUISITIONER)
# -----------------------
class PRCreateView(LoginRequiredMixin, generic.CreateView):
    model = PurchaseRequest
    form_class = PurchaseRequestForm
    template_name = "procurement/pr_form.html"

    def get(self, request):
        form = PurchaseRequestForm()
        formset = PRItemFormSet(prefix="form")
        return render(request, self.template_name, {
            "form": form,
            "formset": formset,
            "is_procurement": False,
        })

    def post(self, request):
        form = PurchaseRequestForm(request.POST)
        formset = PRItemFormSet(request.POST, prefix="form")

        if form.is_valid() and formset.is_valid():
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

def pr_detail(request, pk):
    pr = get_object_or_404(PurchaseRequest, pk=pk)
    items = pr.items.all()

    # Compute total cost per item and grand total
    for item in items:
        item.total_cost = (item.quantity or 0) * (item.unit_cost or 0)
    grand_total = sum(item.total_cost for item in items)

    is_procurement = request.user.groups.filter(name="Procurement").exists()

    return render(request, "procurement/pr_detail.html", {
        "pr": pr,
        "items": items,
        "grand_total": grand_total,
        "is_procurement": is_procurement,
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
        form = ProcurementPRForm(instance=pr)
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
        form = ProcurementPRForm(request.POST, instance=pr)
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

    if request.method == 'POST':
        form = AssignPRNumberForm(request.POST, instance=pr)
        if form.is_valid():
            form.save()
            messages.success(request, "PR Number and Date saved successfully!")
            return redirect('procurement:pr_detail', pk=pr.pk)
    else:
        form = AssignPRNumberForm(instance=pr)

    return render(request, 'procurement/assign_pr_number.html', {'form': form, 'pr': pr})

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
    ordering = ["-id"]

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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pr = self.object
        # Compute grand total here
        grand_total = sum(
            (item.quantity * item.estimated_unit_cost)
            for item in pr.items.all()
        )
        context["grand_total"] = grand_total
        return context

# Update View

class PRUpdateView(LoginRequiredMixin, generic.UpdateView):
    model = PurchaseRequest
    form_class = PurchaseRequestForm
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
        form = self.form_class(request.POST, request.FILES, instance=pr)
        formset = PRItemFormSet(request.POST, instance=pr, prefix="form")

        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, f"Purchase Request {pr.pr_number or pr.id} updated successfully.")
            return redirect("procurement:pr_detail", pk=pr.pk)

        messages.error(request, "Please correct the errors below.")
        return render(request, self.template_name, {
            "form": form,
            "formset": formset,
            "edit_mode": True,
            "pr": pr
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

    # Update status
    pr.status = "submitted"
    pr.save()
    messages.success(request, f"Purchase Request {pr.pr_number or pr.id} has been submitted for verification.")
    return redirect("procurement:pr_detail", pk=pk)