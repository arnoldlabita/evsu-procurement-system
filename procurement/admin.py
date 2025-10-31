from django.contrib import admin
from .models import (
    Supplier,
    PurchaseRequest,
    PRItem,
    RequestForQuotation,
    AgencyProcurementRequest,
    AbstractOfQuotation,
    AOQLine,
    PurchaseOrder,
    Signatory,
)


class PRItemInline(admin.TabularInline):
    model = PRItem
    extra = 0


@admin.register(PRItem)
class PRItemAdmin(admin.ModelAdmin):
    list_display = ("description", "quantity", "unit", "unit_cost")


@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):
    list_display = (
        "pr_number",
        "requisitioner",
        "designation",
        "office_section",
        "funding",
        "status",
        "last_update",
    )
    search_fields = ("pr_number", "requisitioner", "office_section", "funding")
    list_filter = ("status", "office_section", "funding")
    inlines = [PRItemInline]
    actions = ["assign_pr_numbers"]

    def assign_pr_numbers(self, request, queryset):
        for pr in queryset:
            if not pr.pr_number:
                pr.pr_number = f"PR-{pr.created_at.strftime('%Y%m%d')}-{pr.id or '0'}"
                pr.save()
        self.message_user(request, "PR numbers assigned where missing.")

    assign_pr_numbers.short_description = "Assign PR numbers for selected PRs"


# ✅ Register other models normally
admin.site.register(Supplier)
admin.site.register(RequestForQuotation)
admin.site.register(AgencyProcurementRequest)
admin.site.register(AbstractOfQuotation)
admin.site.register(AOQLine)
admin.site.register(PurchaseOrder)

@admin.register(Signatory)
class SignatoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'designation', 'created_at')
    search_fields = ('name', 'designation')