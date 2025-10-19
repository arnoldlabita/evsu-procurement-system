from django.shortcuts import render, redirect, get_object_or_404
from django.views import generic
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import (
    PurchaseRequest, PRItem, Supplier,
    RequestForQuotation, AgencyProcurementRequest,
    AbstractOfQuotation, AOQLine, PurchaseOrder
)
from .forms import (
    PurchaseRequestForm, PRItemFormSet, SupplierForm,
    RFQForm, APRForm, AOQLineFormSet, PurchaseOrderForm
)
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect

def in_procurement_group(user):
    return user.is_authenticated and user.groups.filter(name="Procurement").exists()

def in_requisitioner_group(user):
    return user.is_authenticated and user.groups.filter(name="Requisitioner").exists()

# -----------------------
# DASHBOARD
# -----------------------
class DashboardView(LoginRequiredMixin, generic.TemplateView):
    template_name = "procurement/dashboard.html"  # default fallback

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
        context["user"] = self.request.user
        context["pr_count"] = PurchaseRequest.objects.filter(created_by=self.request.user).count()
        context["rfq_count"] = RequestForQuotation.objects.count()
        context["aoq_count"] = AbstractOfQuotation.objects.count()
        context["po_count"] = PurchaseOrder.objects.count()

        user = self.request.user
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
# PURCHASE REQUEST
# -----------------------
class PRListView(LoginRequiredMixin, generic.ListView):
    model = PurchaseRequest
    template_name = "procurement/pr_list.html"
    context_object_name = "prs"
    ordering = ["-created_at"]


class PRCreateView(LoginRequiredMixin, generic.CreateView):
    model = PurchaseRequest
    form_class = PurchaseRequestForm
    template_name = "procurement/pr_form.html"

    def get(self, request, *args, **kwargs):
        form = self.form_class()
        formset = PRItemFormSet(prefix="form")
        return render(request, self.template_name, {"form": form, "formset": formset})

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST, request.FILES)
        formset = PRItemFormSet(request.POST, prefix="form")
        if form.is_valid() and formset.is_valid():
            pr = form.save(commit=False)
            pr.created_by = request.user
            pr.save()
            formset.instance = pr
            formset.save()
            messages.success(request, "Purchase Request created successfully.")
            return redirect("procurement:pr_detail", pk=pr.pk)
        messages.error(request, "Please check the fields below.")
        return render(request, self.template_name, {"form": form, "formset": formset})


class PRDetailView(LoginRequiredMixin, generic.DetailView):
    model = PurchaseRequest
    template_name = "procurement/pr_detail.html"
    context_object_name = "pr"


@login_required
def assign_pr_number(request, pk):
    pr = get_object_or_404(PurchaseRequest, pk=pk)
    if request.user.is_staff:
        pr.pr_number = f"PR-{timezone.now().strftime('%Y%m%d')}-{pr.id}"
        pr.status = "verified"
        pr.save()
        messages.success(request, f"Assigned PR number: {pr.pr_number}")
    else:
        messages.error(request, "Only procurement staff can assign PR numbers.")
    return redirect("procurement:pr_detail", pk=pk)


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
# RFQ / APR CREATION
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
            messages.success(request, "RFQ created.")
            return redirect("procurement:rfq_preview", pk=rfq.pk)
    else:
        form = RFQForm()
    return render(request, "procurement/create_rfq.html", {"form": form, "pr": pr})


class RFQPreviewView(LoginRequiredMixin, generic.DetailView):
    model = RequestForQuotation
    template_name = "procurement/rfq_preview.html"
    context_object_name = "rfq"

class RFQListView(LoginRequiredMixin, generic.ListView):
    model = RequestForQuotation
    template_name = "procurement/rfq_list.html"
    context_object_name = "rfqs"
    ordering = ["-id"]
    
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
            messages.success(request, "APR created.")
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

def get_template_names(self):
    user = self.request.user
    if user.groups.filter(name="Admin").exists():
        return ["procurement/dashboard_admin.html"]
    elif user.groups.filter(name="Procurement").exists():
        return ["procurement/dashboard_procurement.html"]
    elif user.groups.filter(name="Requisitioner").exists():
        return ["procurement/dashboard_requisitioner.html"]
    return ["procurement/dashboard_unauthorized.html"]

from django.contrib.auth.views import LoginView
from django.shortcuts import redirect

class EVSULoginView(LoginView):
    template_name = "registration/login.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("procurement:dashboard")
        return super().dispatch(request, *args, **kwargs)
