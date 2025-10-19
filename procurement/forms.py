from django import forms
from .models import PurchaseRequest, PRItem, Supplier, RequestForQuotation, AgencyProcurementRequest, AbstractOfQuotation, AOQLine, PurchaseOrder
from django.forms import inlineformset_factory
from .models import PurchaseRequest, PRItem

class PurchaseRequestForm(forms.ModelForm):
    class Meta:
        model = PurchaseRequest
        fields = ["requesting_office", "purpose", "attachments"]

    PRItemFormSet = inlineformset_factory(
    PurchaseRequest,
    PRItem,
    fields=["description", "quantity", "unit", "estimated_unit_cost"],
    extra=0,
    can_delete=True
    )

class PRItemForm(forms.ModelForm):
    class Meta:
        model = PRItem
        fields = ["description", "quantity", "unit", "estimated_unit_cost"]
        widgets = {
            "description": forms.Textarea(attrs={
                "class": "form-control form-control-sm",
                "rows": 1,  # ✅ Make it shorter
                "style": "resize:none; min-width:180px;"
            }),
            "quantity": forms.NumberInput(attrs={"class": "form-control form-control-sm", "style": "width:90px;"}),
            "unit": forms.Select(attrs={"class": "form-select form-select-sm", "style": "width:110px;"}),
            "estimated_unit_cost": forms.NumberInput(attrs={"class": "form-control form-control-sm", "style": "width:120px;"}),
        }
        
PRItemFormSet = forms.inlineformset_factory(PurchaseRequest, PRItem, form=PRItemForm, extra=1, can_delete=True)

class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "address", "contact_person", "contact_no", "tin", "accredited"]

class RFQForm(forms.ModelForm):
    class Meta:
        model = RequestForQuotation
        fields = ["date"]

class APRForm(forms.ModelForm):
    class Meta:
        model = AgencyProcurementRequest
        fields = ["requesting_agency"]

class AOQForm(forms.ModelForm):
    class Meta:
        model = AbstractOfQuotation
        fields = []

class AOQLineForm(forms.ModelForm):
    class Meta:
        model = AOQLine
        fields = ["pr_item", "supplier", "unit_price", "responsive"]

AOQLineFormSet = forms.inlineformset_factory(AbstractOfQuotation, AOQLine, form=AOQLineForm, extra=1, can_delete=True)

class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ["supplier", "place_of_delivery", "date_of_delivery", "submission_date", "receiving_office"]
