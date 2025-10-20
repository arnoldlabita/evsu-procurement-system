from django import forms
from django.forms import inlineformset_factory
from .models import (
    PurchaseRequest, PRItem, Supplier,
    RequestForQuotation, AgencyProcurementRequest,
    AbstractOfQuotation, AOQLine, PurchaseOrder
)

# -------------------------
# PURCHASE REQUEST FORMS
# -------------------------

# Requisitioner form: cannot set PR number or date
class PurchaseRequestForm(forms.ModelForm):
    class Meta:
        model = PurchaseRequest
        fields = [
            'requesting_office',
            'fund_cluster',
            'responsibility_center_code',
            'purpose'
        ]
        widgets = {
            'purpose': forms.Textarea(attrs={'rows': 1}),
        }

# Procurement staff form: can assign PR number and date
class ProcurementPRForm(forms.ModelForm):
    class Meta:
        model = PurchaseRequest
        fields = [
            'pr_number',
            'pr_date',
            'requesting_office',
            'fund_cluster',
            'responsibility_center_code',
            'purpose'
        ]
        widgets = {
            'pr_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'purpose': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'pr_number': forms.TextInput(attrs={'class': 'form-control'}),
        }

# -------------------------
# PR ITEM FORM
# -------------------------
class PRItemForm(forms.ModelForm):
    class Meta:
        model = PRItem
        fields = ["stock_no", "description", "quantity", "unit", "unit_cost"]
        widgets = {
            "stock_no": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "description": forms.Textarea(attrs={
                "class": "form-control form-control-sm",
                "rows": 1,
                "style": "resize:none; min-width:180px;"
            }),
            "quantity": forms.NumberInput(attrs={
                "class": "form-control form-control-sm",
                "style": "width:90px;"
            }),
            "unit": forms.Select(attrs={
                "class": "form-select form-select-sm",
                "style": "width:110px;"
            }),
            "unit_cost": forms.NumberInput(attrs={
                "class": "form-control form-control-sm",
                "style": "width:120px;"
            }),
        }

class AssignPRNumberForm(forms.ModelForm):
    class Meta:
        model = PurchaseRequest
        fields = ['pr_number', 'pr_date']
        widgets = {
            'pr_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'pr_number': forms.TextInput(attrs={'class': 'form-control'}),
        }
        
# Inline formset for PR items
PRItemFormSet = inlineformset_factory(
    PurchaseRequest,
    PRItem,
    form=PRItemForm,
    extra=1,
    can_delete=True
)

# -------------------------
# SUPPLIER FORM
# -------------------------
class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "address", "contact_person", "contact_no", "tin", "accredited"]

# -------------------------
# REQUEST FOR QUOTATION (RFQ) FORM
# -------------------------
class RFQForm(forms.ModelForm):
    class Meta:
        model = RequestForQuotation
        fields = ["date"]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }

# -------------------------
# AGENCY PROCUREMENT REQUEST (APR) FORM
# -------------------------
class APRForm(forms.ModelForm):
    class Meta:
        model = AgencyProcurementRequest
        fields = ["requesting_agency"]

# -------------------------
# ABSTRACT OF QUOTATION (AOQ) FORMS
# -------------------------
class AOQForm(forms.ModelForm):
    class Meta:
        model = AbstractOfQuotation
        fields = []

class AOQLineForm(forms.ModelForm):
    class Meta:
        model = AOQLine
        fields = ["pr_item", "supplier", "unit_price", "responsive"]

AOQLineFormSet = inlineformset_factory(
    AbstractOfQuotation,
    AOQLine,
    form=AOQLineForm,
    extra=1,
    can_delete=True
)

# -------------------------
# PURCHASE ORDER FORM
# -------------------------
class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = [
            "supplier",
            "place_of_delivery",
            "date_of_delivery",
            "submission_date",
            "receiving_office"
        ]
        widgets = {
            "date_of_delivery": forms.DateInput(attrs={'type': 'date'}),
            "submission_date": forms.DateInput(attrs={'type': 'date'}),
        }
