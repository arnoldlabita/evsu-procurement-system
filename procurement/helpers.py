from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

def compute_aoq_totals(aoq):
    summary = aoq.summarize()
    grand_total = sum(v['total'] for v in summary.values())
    return {"summary": summary, "grand_total": grand_total}

@transaction.atomic
def award_and_create_po(aoq, supplier_id, awarded_by):
    po = aoq.award(supplier_id, awarded_by=awarded_by)
    return po

def award_aoq_and_create_po(aoq, supplier_id, awarded_by):
    from .models import Supplier, PurchaseOrder
    with transaction.atomic():
        supplier = Supplier.objects.get(pk=supplier_id)
        # validate supplier has responsive lines
        if not aoq.lines.filter(supplier=supplier, responsive=True).exists():
            raise ValidationError("Supplier has no responsive lines in AOQ.")

        po = PurchaseOrder.objects.create(
            aoq=aoq,
            supplier=supplier,
            created_by=awarded_by,
            submission_date=timezone.now().date(),
            receiving_office="To be set"
        )
        po.po_number = f"PO-{timezone.now().strftime('%Y%m%d')}-{po.id}"
        po.save()

        # set award fields on AOQ
        aoq.awarded_to = supplier
        aoq.awarded_at = timezone.now()
        aoq.awarded_by = awarded_by
        aoq.save(update_fields=['awarded_to','awarded_at','awarded_by'])

        # update PR
        pr = aoq.rfq.purchase_request
        pr.status = "po_issued"
        pr.last_update = timezone.now()
        pr.save(update_fields=['status','last_update'])

        return po