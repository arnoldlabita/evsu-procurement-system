from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from .models import (
    PurchaseRequest, PRItem, Supplier,
    RequestForQuotation, AgencyProcurementRequest,
    AbstractOfQuotation, AOQLine, PurchaseOrder, Bid, BidLine
)

# -------------------------
# PURCHASE REQUEST FORMS
# -------------------------

# Requisitioner form (for creating PR)
class RequisitionerPRForm(forms.ModelForm):
    FUNDING_CHOICES = [
        ("IGF", "Internally Generated Fund (IGF)"),
        ("RAF", "Regular Agency Fund (RAF)"),
        ("TRF", "Trust Receipt Fund (TRF)"),
        ("BRF", "Business Related Fund (BRF)"),
    ]

    funding = forms.ChoiceField(
        choices=FUNDING_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
        required=False,
    )

    class Meta:
        model = PurchaseRequest
        fields = [
            "requisitioner",
            "designation",
            "office_section",
            "purpose",
            "funding",
            "attachments",
        ]
        widgets = {
            "requisitioner": forms.TextInput(attrs={"class": "form-control"}),
            "designation": forms.TextInput(attrs={"class": "form-control"}),
            "office_section": forms.TextInput(attrs={"class": "form-control"}),
            "purpose": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "attachments": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }


# Procurement staff form (for assigning PR number and updating metadata)
class ProcurementStaffPRForm(forms.ModelForm):
    class Meta:
        model = PurchaseRequest
        fields = [
            "pr_number",
            "pr_date",
            "status",
            "purpose",
            "attachments",
        ]
        widgets = {
            "pr_number": forms.TextInput(attrs={'class': 'form-control'}),
            "pr_date": forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            "status": forms.Select(attrs={'class': 'form-select'}),
            "purpose": forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            "attachments": forms.ClearableFileInput(attrs={"class": "form-control"}),
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


# -------------------------
# ASSIGN PR NUMBER FORM
# -------------------------
class AssignPRNumberForm(forms.ModelForm):
    class Meta:
        model = PurchaseRequest
        fields = ['pr_number', 'pr_date']
        widgets = {
            'pr_number': forms.TextInput(attrs={'class': 'form-control'}),
            'pr_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
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
        fields = ["name", "address", "contact_person", "contact_no", "contact_email", "tin", "accredited"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "address": forms.TextInput(attrs={"class": "form-control"}),
            "contact_person": forms.TextInput(attrs={"class": "form-control"}),
            "contact_no": forms.TextInput(attrs={"class": "form-control"}),
            "contact_email": forms.TextInput(attrs={"class": "form-control"}),
            "tin": forms.TextInput(attrs={"class": "form-control"}),
            "accredited": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


# -------------------------
# REQUEST FOR QUOTATION (RFQ) FORM
# -------------------------
class RFQForm(forms.ModelForm):
    class Meta:
        model = RequestForQuotation
        fields = ["date"]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

class BidForm(forms.ModelForm):
    class Meta:
        model = Bid
        fields = ["supplier", "status", "remarks"]
        widgets = {
            "supplier": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "remarks": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, *args, rfq=None, **kwargs):
        """
        Accept 'rfq' so we can validate duplicate suppliers for that RFQ at the form level.
        """
        self.rfq = rfq
        super().__init__(*args, **kwargs)

    def clean_supplier(self):
        supplier = self.cleaned_data.get("supplier")
        if not supplier:
            return supplier
        # Prevent duplicate supplier for the same RFQ (additional to model constraint)
        if self.rfq and Bid.objects.filter(rfq=self.rfq, supplier=supplier).exclude(pk=getattr(self.instance, "pk", None)).exists():
            raise ValidationError("This supplier already has a bid for this RFQ.")
        return supplier

from django import forms
from .models import BidLine, PRItem, Bid

class BidLineForm(forms.ModelForm):
    class Meta:
        model = BidLine
        fields = ["pr_item", "offer", "unit_price", "compliant"]
        widgets = {
            # Make PR item appear as static text (read-only, not dropdown)
            "pr_item": forms.TextInput(attrs={
                "class": "form-control-plaintext form-control-sm",
                "readonly": True
            }),
            # Add Offer text box
            "offer": forms.TextInput(attrs={
                "class": "form-control form-control-sm",
                "placeholder": "Enter offer (optional)"
            }),
            # Make Unit Price optional, no default prompt
            "unit_price": forms.NumberInput(attrs={
                "class": "form-control form-control-sm",
                "placeholder": ""
            }),
            "compliant": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Make 'unit_price' optional
        self.fields["unit_price"].required = False

        # If bound to a Bid, set PR items properly
        if self.instance and getattr(self.instance, "bid", None):
            rfq = getattr(self.instance.bid, "rfq", None)
            if rfq:
                self.fields["pr_item"].queryset = PRItem.objects.filter(
                    purchase_request=rfq.purchase_request
                )


BidLineFormSet = inlineformset_factory(
    Bid, BidLine, form=BidLineForm, extra=0, can_delete=True
)


# -------------------------
# AGENCY PROCUREMENT REQUEST (APR) FORM
# -------------------------
class APRForm(forms.ModelForm):
    class Meta:
        model = AgencyProcurementRequest
        fields = ["requesting_agency"]
        widgets = {
            "requesting_agency": forms.TextInput(attrs={"class": "form-control"}),
        }


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
        widgets = {
            "pr_item": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "supplier": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "unit_price": forms.NumberInput(attrs={"class": "form-control form-control-sm"}),
            "responsive": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


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
            "receiving_office",
        ]
        widgets = {
            "supplier": forms.Select(attrs={'class': 'form-select'}),
            "place_of_delivery": forms.TextInput(attrs={'class': 'form-control'}),
            "date_of_delivery": forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            "submission_date": forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            "receiving_office": forms.TextInput(attrs={'class': 'form-control'}),
        }

class ModeOfProcurementForm(forms.ModelForm):
    class Meta:
        model = PurchaseRequest
        fields = ["mode_of_procurement", "negotiated_type"]
        widgets = {
            "mode_of_procurement": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "negotiated_type": forms.Select(attrs={"class": "form-select form-select-sm"}),
        }

import re

class PurchaseRequestForm(forms.ModelForm):
    class Meta:
        model = PurchaseRequest
        fields = '__all__'

    def clean_pr_number(self):
        pr_number = self.cleaned_data.get('pr_number')

        # ✅ Check format
        pattern = r'^\d{2}-\d{4}-\d{2}\s.+$'
        if not re.match(pattern, pr_number):
            raise ValidationError("PR number must follow the format: (e.g., 10-0042-25 Requesting Office).")

        # ✅ Check duplicates (case-insensitive)
        if PurchaseRequest.objects.filter(pr_number__iexact=pr_number).exists():
            raise ValidationError("This PR number already exists. Please use a unique one.")

        return pr_number
