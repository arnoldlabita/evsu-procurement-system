from django.contrib.auth import get_user_model
from django.db import models
from django.urls import reverse
from django.db import transaction
from django.utils import timezone
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError

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
    contact_email = models.CharField(max_length=50, blank=True)
    tin = models.CharField(max_length=50, blank=True)
    accredited = models.BooleanField(default=False)

    def __str__(self):
        return self.name

class PurchaseRequest(models.Model):
    STATUS_CHOICES = [
        # Stage 1: Requisition
        ("draft", "Draft"),
        ("submitted", "Submitted for Verification"),

        # Stage 2: Verification / Approval
        ("verified", "Verified"),
        ("endorsed", "Endorsed for Approval"),
        ("approved", "Approved"),

        # Stage 3A: Small Value Procurement
        ("for_mop", "For BACRes. MOP"),
        ("for_rfq", "For RFQ Preparation"),
        ("for_award", "For BACRes. Award"),
        ("for_po", "For PO Preparation"),
        ("po_issued", "PO Issued"),
        ("delivered", "Items Delivered"),
        ("inspected", "Inspected"),
        ("closed", "Closed"),

        # Stage 3B: Competitive Bidding
        ("for_pb", "For Public Bidding"),
        ("pre_bid", "Pre-Bid Conference"),
        ("bidding_open", "Bidding Open"),
        ("bid_evaluation", "Bid Evaluation"),
        ("post_qualification", "Post-Qualification"),
        ("bac_resolution", "BAC Resolution Issued"),
        ("notice_of_award", "Notice of Award Issued"),
        ("contract_preparation", "Contract Preparation"),
        ("contract_signed", "Contract Signed"),
        ("notice_to_proceed", "Notice to Proceed Issued"),
        ("delivery_completed", "Delivery Completed"),
        ("payment_processing", "Payment Processing"),

        # Exceptions
        ("cancelled", "Cancelled"),
        ("failed_bidding", "Failed Bidding"),
        ("disqualified", "Disqualified Bidder"),
    ]

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="draft")

    FUNDING_CHOICES = [
        ("IGF", "Internally Generated Fund (IGF)"),
        ("RAF", "Regular Agency Fund (RAF)"),
        ("TRF", "Trust Receipt Fund (TRF)"),
        ("BRF", "Business Related Fund (BRF)"),
    ]

    MODE_OF_PROCUREMENT_CHOICES = [
        ("Competitive Bidding", "Competitive Bidding"),
        ("Limited Source Bidding", "Limited Source Bidding"),
        ("Competitive Dialogue", "Competitive Dialogue"),
        ("Unsolicited Offer with Bid Matching", "Unsolicited Offer with Bid Matching"),
        ("Direct Contracting", "Direct Contracting"),
        ("Direct Acquisition", "Direct Acquisition"),
        ("Repeat Order", "Repeat Order"),
        ("Small Value Procurement", "Small Value Procurement"),
        ("Negotiated Procurement", "Negotiated Procurement"),
        ("Direct Sales", "Direct Sales"),
        ("Direct Procurement for Science, Technology and Innovation", "Direct Procurement for Science, Technology and Innovation"),
    ]

    NEGOTIATED_SUB_CHOICES = [
        ("Two Failed Biddings", "Two Failed Biddings"),
        ("Emergency Cases", "Emergency Cases"),
        ("Take-over of Contracts", "Take-over of Contracts"),
        ("Adjacent or Contiguous", "Adjacent or Contiguous"),
        ("Agency-to-Agency", "Agency-to-Agency"),
        ("Scientific, Scholarly or Artistic Work, Exclusive Technology and Media Services",
         "Scientific, Scholarly or Artistic Work, Exclusive Technology and Media Services"),
        ("Highly Technical Consultants", "Highly Technical Consultants"),
        ("Defense Cooperation Agreements and Inventory-Based Items",
         "Defense Cooperation Agreements and Inventory-Based Items"),
        ("Lease of Real Property and Venue", "Lease of Real Property and Venue"),
        ("Non-Government Organization (NGO) Participation", "Non-Government Organization (NGO) Participation"),
        ("Community Participation", "Community Participation"),
        ("United Nations (UN) Agencies, International Organizations or International Financing Institutions",
         "United Nations (UN) Agencies, International Organizations or International Financing Institutions"),
        ("Direct Retail Purchase of Petroleum Fuel, Oil and Lubricant Products, Electronic Charging Devices, and Online Subscriptions",
         "Direct Retail Purchase of Petroleum Fuel, Oil and Lubricant Products, Electronic Charging Devices, and Online Subscriptions"),
    ]

    mode_of_procurement = models.CharField(
        max_length=150,
        choices=MODE_OF_PROCUREMENT_CHOICES,
        blank=True,
        null=True,
    )

    negotiated_type = models.CharField(
        max_length=200,
        choices=NEGOTIATED_SUB_CHOICES,
        blank=True,
        null=True,
        help_text="If 'Negotiated Procurement' is selected, specify the type here."
    )

    # --- Requestor Info ---
    requisitioner = models.CharField(max_length=255, blank=True, null=True)
    designation = models.CharField(max_length=255, blank=True, null=True)
    office_section = models.CharField(max_length=255, blank=True, null=True)
    purpose = models.TextField(blank=True, null=True)
    funding = models.CharField(
        max_length=50,
        choices=FUNDING_CHOICES,
        blank=True,
        null=True,
        help_text="Select the fund source"
    )
    attachments = models.FileField(upload_to="pr_attachments/", blank=True, null=True)


    # --- PR Metadata ---
    pr_number = models.CharField(
        max_length=100,
        unique=True,  # ✅ ensures uniqueness
        validators=[
            RegexValidator(
                regex=r'^\d{2}-\d{4}-\d{2}\s.+$',
                message="PR number must follow the format: (10-0042-25 Requesting Office)."
            )
        ],
        help_text="Format: 10-0042-25 Requesting Office)",
        blank=True,
        null=True,
    )
    pr_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")

    # --- System Info ---
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="purchase_requests")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_update = models.DateTimeField(default=timezone.now)

    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"PR-{self.pr_number or self.id}"

    def assign_pr_number(self):
        if not self.pr_number:
            self.pr_number = f"PR-{timezone.now().strftime('%Y%m%d')}-{self.id}"
            self.save()

    def __str__(self):
        return self.pr_number or f"PR (draft) {self.id}"

    def total_amount(self):
        return sum(item.total_cost() for item in self.items.all())
    
    def breakdown_by_budget(self):
        """
        Returns dict: { 'PS': Decimal(...), 'MOOE': Decimal(...), ... }
        """
        from collections import defaultdict
        totals = defaultdict(lambda: 0)
        for item in self.items.all():
            totals[item.budget_category] += (item.quantity or 0) * (item.unit_cost or 0)
        return dict(totals)


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

    BUDGET_CATEGORIES = [
    ("PS", "Personal Services"),
    ("MOOE", "Maintenance & Other Operating Expenses"),
    ("CO", "Capital Outlay"),
    ("OTHER", "Other"),
    ]

    purchase_request = models.ForeignKey(
        "PurchaseRequest", on_delete=models.CASCADE, related_name="items"
    )
    stock_no = models.CharField(max_length=50, blank=True, null=True)
    description = models.TextField()
    quantity = models.PositiveIntegerField()
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)  # ✅ renamed field
    budget_category = models.CharField(max_length=20, choices=BUDGET_CATEGORIES, default="MOOE")

    def total_cost(self):
        return self.quantity * self.unit_cost

    def __str__(self):
        return f"{self.description} ({self.unit})"

class RequestForQuotation(TimestampedModel):
    rfq_number = models.CharField(max_length=50, blank=True, null=True, unique=True)
    purchase_request = models.OneToOneField(PurchaseRequest, related_name="rfq", on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now)
    resolution = models.TextField(blank=True, null=True)
    resolution_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="rfq_resolutions_by")
    resolution_at = models.DateTimeField(null=True, blank=True)
    # other fields as required

    def __str__(self):
        return self.rfq_number or f"RFQ for {self.purchase_request}"

# --- Bid models for RFQ processing ---
class Bid(models.Model):
    STATUS_CHOICES = [
        ("submitted", "Submitted"),
        ("withdrawn", "Withdrawn"),
        ("awarded", "Awarded"),
    ]

    rfq = models.ForeignKey(
        "RequestForQuotation", related_name="bids", on_delete=models.CASCADE
    )
    supplier = models.ForeignKey("Supplier", on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="submitted")
    remarks = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="bids_created")

    class Meta:
        unique_together = ("rfq", "supplier")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Bid: {self.supplier} on {self.rfq}"

    def total_bid_amount(self):
        # Sum over related BidLine if present
        return sum((line.total_cost() or 0) for line in self.lines.all())
    
    def completeness_status(self):
        """Return True if bid has lines for every PRItem in the RFQ's PR."""
        pr_items = list(self.rfq.purchase_request.items.values_list('pk', flat=True))
        bid_item_ids = list(self.lines.values_list('pr_item__pk', flat=True))
        return set(pr_items) <= set(bid_item_ids)

    def responsive_status(self):
        """Return True if all lines marked responsive/compliant and have valid prices."""
        if not self.completeness_status():
            return False
        for line in self.lines.all():
            if not line.responsive if hasattr(line, 'responsive') else line.compliant:
                return False
            if not line.is_valid_price():
                return False
        return True

class BidLine(models.Model):
    bid = models.ForeignKey("Bid", related_name="lines", on_delete=models.CASCADE)
    pr_item = models.ForeignKey("PRItem", on_delete=models.CASCADE)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    compliant = models.BooleanField(default=True)

    def total_cost(self):
        return (self.pr_item.quantity or 0) * (self.unit_price or 0)

    def __str__(self):
        return f"{self.pr_item} — {self.unit_price}"
    
    def is_valid_price(self):
        # optional business rule: price > 0
        try:
            return (self.unit_price is not None) and (self.unit_price > 0)
        except:
            return False


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
    awarded_to = models.ForeignKey(
    Supplier, null=True, blank=True, on_delete=models.SET_NULL, related_name="awarded_aoqs"
    )
    awarded_at = models.DateTimeField(null=True, blank=True)
    awarded_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="aoqs_awarded_by")
    computed_summary = models.JSONField(blank=True, null=True)  # Django 3.1+; else use TextField

    def __str__(self):
        return self.aoq_number or f"AOQ for {self.rfq}"
    
    def compute_lcrb(self):
        """
        Compute Lowest Compliant Responsive Bid (LCRB) per PRItem.
        Returns dict: { pr_item.pk: BidLine (winning line) }
        """
        winners = {}
        for pr_item in self.rfq.purchase_request.items.all():
            # filter responsive lines for this item
            responsive_lines = self.rfq.aoq.lines.filter(pr_item=pr_item, responsive=True).order_by("unit_price")
            if responsive_lines.exists():
                winners[pr_item.pk] = responsive_lines.first()
        return winners

    def summarize(self):
        """
        Summarize total per supplier and grand totals. Returns dict summary.
        """
        summary = {}
        for line in self.lines.select_related('supplier','pr_item'):
            sup = line.supplier
            summary.setdefault(sup.pk, {"supplier": sup, "total": 0, "lines": []})
            line_total = (line.unit_price or 0) * (line.pr_item.quantity or 0)
            summary[sup.pk]["total"] += line_total
            summary[sup.pk]["lines"].append(line)
        return summary

    @transaction.atomic
    def award(self, supplier_id, awarded_by=None):
        """
        Mark AOQ as awarded to supplier_id and create PurchaseOrder(s).
        Atomic: either award + PO creation succeed or roll back.
        """
        # Basic validation
        aoq = self
        supplier = Supplier.objects.get(pk=supplier_id)  # may raise
        # optional: ensure supplier present in AOQ lines
        if not aoq.lines.filter(supplier=supplier, responsive=True).exists():
            raise ValidationError("Supplier has no responsive lines in AOQ.")

        # create PO - you may choose to create one PO per supplier or one consolidated PO
        po = PurchaseOrder.objects.create(
            aoq=aoq,
            supplier=supplier,
            created_by=awarded_by,
            submission_date=timezone.now().date(),
            receiving_office="To be set"
        )
        po.po_number = f"PO-{timezone.now().strftime('%Y%m%d')}-{po.id}"
        po.save()

        # mark AOQ as awarded
        aoq.awarded_to = supplier  # add field? if not present, set notes/status.
        aoq.save(update_fields=['awarded_to'])

        # update related PR status (optional)
        pr = aoq.rfq.purchase_request
        pr.status = "po_issued"
        pr.last_update = timezone.now()
        pr.save(update_fields=['status','last_update'])

        return po
    
    def supplier_summary(self):
        """
        Returns a list of dicts: [{supplier, total, responsive_count, lines}, ...]
        ```
        """
        summary = {}
        for line in self.lines.select_related("supplier", "pr_item"):
            sup = line.supplier
            line_total = (line.unit_price or 0) * (line.pr_item.quantity or 0)
            if sup.pk not in summary:
                summary[sup.pk] = {"supplier": sup, "total": 0, "lines": [], "responsive_count": 0}
            summary[sup.pk]["total"] += line_total
            summary[sup.pk]["lines"].append(line)
            if getattr(line, "responsive", True) or getattr(line, "compliant", True):
                summary[sup.pk]["responsive_count"] += 1
        # return sorted by total ascending (lowest bid first)
        result = sorted(summary.values(), key=lambda s: s["total"])
        return result

    def winning_supplier_and_savings(self):
        """
        Determine current winning supplier by lowest total among responsive suppliers.
        Returns (supplier, winning_total, pr_total, savings, pct_savings)
        """
        pr_total = self.rfq.purchase_request.total_amount()
        suppliers = self.supplier_summary()
        # find first supplier with responsive_count == number_of_pr_items (complete & responsive)
        num_items = self.rfq.purchase_request.items.count()
        winner = None
        for s in suppliers:
            if s["responsive_count"] >= num_items:
                winner = s
                break
        if not winner:
            return None, None, pr_total, None, None

        winning_total = winner["total"]
        savings = (pr_total - winning_total)
        pct = (savings / pr_total * 100) if pr_total else 0
        return winner["supplier"], winning_total, pr_total, savings, pct

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
    
class Signatory(models.Model):
    name = models.CharField(max_length=255)
    designation = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} — {self.designation}"

class ActionLog(models.Model):
    actor = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=200)
    target_type = models.CharField(max_length=50, blank=True, null=True)
    target_id = models.IntegerField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
