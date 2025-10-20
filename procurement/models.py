from django.contrib.auth import get_user_model
from django.db import models
from django.urls import reverse
from django.utils import timezone

User = get_user_model()

class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="%(class)s_created")
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="%(class)s_updated")
    class Meta:
        abstract = True

class Supplier(TimestampedModel):
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=500, blank=True)
    contact_person = models.CharField(max_length=255, blank=True)
    contact_no = models.CharField(max_length=50, blank=True)
    tin = models.CharField(max_length=50, blank=True)
    accredited = models.BooleanField(default=False)

    def __str__(self):
        return self.name

class PurchaseRequest(TimestampedModel):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("verified", "Verified"),
        ("closed", "Closed"),
    ]

    pr_number = models.CharField(max_length=50, blank=True, unique=True, null=True)
    pr_date = models.DateField(default=timezone.now)
    requesting_office = models.CharField(max_length=255)
    fund_cluster = models.CharField(max_length=100, blank=True, null=True)  # ✅ new
    responsibility_center_code = models.CharField(max_length=100, blank=True, null=True)  # ✅ new
    purpose = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    attachments = models.FileField(upload_to="pr_attachments/", null=True, blank=True)

    def assign_pr_number(self):
        if not self.pr_number:
            self.pr_number = f"PR-{timezone.now().strftime('%Y%m%d')}-{self.id}"
            self.save()

    def __str__(self):
        return self.pr_number or f"PR (draft) {self.id}"
    
    def total_amount(self):
        return sum(item.total_cost() for item in self.items.all())

class PRItem(models.Model):
    UNIT_CHOICES = [
        ("amp", "Ampere"), ("bag", "Bag"), ("bar", "Bar"), ("batch", "Batch"),
        ("block", "Block"), ("board", "Board"), ("book", "Book"), ("bottle", "Bottle"),
        ("box", "Box"), ("bundle", "Bundle"), ("bunch", "Bunch"), ("can", "Can"),
        ("carton", "Carton"), ("case", "Case"), ("cm", "Centimeter"),
        ("cuft", "Cubic Foot"), ("cum", "Cubic Meter"), ("cup", "Cup"), ("day", "Day"),
        ("dozen", "Dozen"), ("drum", "Drum"), ("each", "Each"), ("envelope", "Envelope"),
        ("ft", "Foot"), ("gal", "Gallon"), ("g", "Gram"), ("hour", "Hour"),
        ("in", "Inch"), ("jar", "Jar"), ("job", "Job"), ("jug", "Jug"),
        ("kg", "Kilogram"), ("km", "Kilometer"), ("length", "Length"), ("liter", "Liter"),
        ("lot", "Lot"), ("m", "Meter"), ("mg", "Milligram"), ("ml", "Milliliter"),
        ("mm", "Millimeter"), ("month", "Month"), ("pad", "Pad"), ("pail", "Pail"),
        ("pair", "Pair"), ("pack", "Pack"), ("packet", "Packet"), ("panel", "Panel"),
        ("pc", "Piece"), ("plate", "Plate"), ("pot", "Pot"), ("pouch", "Pouch"),
        ("quart", "Quart"), ("ream", "Ream"), ("roll", "Roll"), ("sack", "Sack"),
        ("sachet", "Sachet"), ("set", "Set"), ("sheet", "Sheet"),
        ("sqft", "Square Foot"), ("sqm", "Square Meter"), ("stick", "Stick"),
        ("strip", "Strip"), ("tank", "Tank"), ("tray", "Tray"), ("tube", "Tube"),
        ("unit", "Unit"), ("volt", "Volt"), ("watt", "Watt"), ("yard", "Yard"),
        ("year", "Year"), ("others", "Others (Specify)"),
    ]

    purchase_request = models.ForeignKey(
        "PurchaseRequest", on_delete=models.CASCADE, related_name="items"
    )
    stock_no = models.CharField(max_length=50, blank=True, null=True)
    description = models.TextField()
    quantity = models.PositiveIntegerField()
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)  # ✅ renamed field
    
    def total_cost(self):
        return self.quantity * self.unit_cost

    def __str__(self):
        return f"{self.description} ({self.unit})"

class RequestForQuotation(TimestampedModel):
    rfq_number = models.CharField(max_length=50, blank=True, null=True, unique=True)
    purchase_request = models.OneToOneField(PurchaseRequest, related_name="rfq", on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now)
    # other fields as required

    def __str__(self):
        return self.rfq_number or f"RFQ for {self.purchase_request}"

class AgencyProcurementRequest(TimestampedModel):
    apr_number = models.CharField(max_length=50, blank=True, null=True, unique=True)
    purchase_request = models.OneToOneField(PurchaseRequest, related_name="apr", on_delete=models.CASCADE)
    requesting_agency = models.CharField(max_length=255, blank=True)
    # store other APR-specific fields here

    def __str__(self):
        return self.apr_number or f"APR for {self.purchase_request}"

class AbstractOfQuotation(TimestampedModel):
    aoq_number = models.CharField(max_length=50, blank=True, null=True, unique=True)
    rfq = models.OneToOneField(RequestForQuotation, related_name="aoq", on_delete=models.CASCADE)
    verified = models.BooleanField(default=False)

    def __str__(self):
        return self.aoq_number or f"AOQ for {self.rfq}"

class AOQLine(models.Model):
    aoq = models.ForeignKey(AbstractOfQuotation, related_name="lines", on_delete=models.CASCADE)
    pr_item = models.ForeignKey(PRItem, on_delete=models.CASCADE)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    responsive = models.BooleanField(default=True)  # whether bid is responsive

    def line_total(self):
        return self.unit_price * self.pr_item.quantity

class PurchaseOrder(TimestampedModel):
    po_number = models.CharField(max_length=50, blank=True, null=True, unique=True)
    aoq = models.ForeignKey(AbstractOfQuotation, related_name="purchase_orders", on_delete=models.CASCADE)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)
    place_of_delivery = models.CharField(max_length=255, blank=True)
    date_of_delivery = models.DateField(null=True, blank=True)
    submission_date = models.DateField(null=True, blank=True)  # monitoring field
    receiving_office = models.CharField(max_length=255, blank=True)  # monitoring field

    def __str__(self):
        return self.po_number or f"PO for {self.supplier}"
