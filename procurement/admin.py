from django.contrib import admin
from .models import Supplier, PurchaseRequest, PRItem, RequestForQuotation, AgencyProcurementRequest, AbstractOfQuotation, AOQLine, PurchaseOrder

class PRItemInline(admin.TabularInline):
    model = PRItem
    extra = 0

@admin.register(PRItem)
class PRItemAdmin(admin.ModelAdmin):
    list_display = ("description", "quantity", "unit", "estimated_unit_cost")
    
@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):
    list_display = ("pr_number", "requesting_office", "status", "created_at")
    inlines = [PRItemInline]
    actions = ["assign_pr_numbers"]

    def assign_pr_numbers(self, request, queryset):
        for pr in queryset:
            if not pr.pr_number:
                pr.pr_number = f"PR-{pr.created_at.strftime('%Y%m%d')}-{pr.id or '0'}"
                pr.save()
        self.message_user(request, "PR numbers assigned where missing.")
    assign_pr_numbers.short_description = "Assign PR numbers for selected PRs"

admin.site.register(Supplier)
admin.site.register(RequestForQuotation)
admin.site.register(AgencyProcurementRequest)
admin.site.register(AbstractOfQuotation)
admin.site.register(AOQLine)
admin.site.register(PurchaseOrder)
