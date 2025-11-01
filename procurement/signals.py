from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import AbstractOfQuotation, PurchaseOrder

@receiver(post_save, sender=AbstractOfQuotation)
def aoq_post_save(sender, instance, created, **kwargs):
    if created:
        # mark RFQ/PR status to AOQ generated
        rfq = instance.rfq
        pr = rfq.purchase_request
        pr.status = "for_award"  # or a meaningful code
        pr.save(update_fields=['status'])

@receiver(post_save, sender=PurchaseOrder)
def po_post_save(sender, instance, created, **kwargs):
    if created:
        # mark PR status PO issued
        aoq = instance.aoq
        pr = aoq.rfq.purchase_request
        pr.status = "po_issued"
        pr.save(update_fields=['status'])
