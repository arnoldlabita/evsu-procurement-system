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
    Bid,
    BidLine
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
admin.site.register(AgencyProcurementRequest)
admin.site.register(AOQLine)


class BidLineInline(admin.TabularInline):
    model = BidLine
    extra = 0

@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ("rfq", "supplier", "status", "total_bid_amount", "created_at")
    list_filter = ("status", "rfq")
    search_fields = ("rfq__rfq_number", "supplier__name")
    inlines = [BidLineInline]

class RFQBidInline(admin.TabularInline):
    model = Bid
    extra = 0

@admin.register(RequestForQuotation)
class RFQAdmin(admin.ModelAdmin):
    list_display = ("rfq_number", "purchase_request", "date", "created_by")
    list_filter = ("date",)
    search_fields = ("rfq_number", "purchase_request__pr_number")
    inlines = [RFQBidInline]


@admin.register(Signatory)
class SignatoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'designation', 'created_at')
    search_fields = ('name', 'designation')

@admin.register(AbstractOfQuotation)
class AOQAdmin(admin.ModelAdmin):
    list_display = ("aoq_number", "rfq", "awarded_to", "awarded_at", "verified")
    search_fields = ("aoq_number", "rfq__rfq_number", "awarded_to__name")
    readonly_fields = ("awarded_at","awarded_by")

@admin.register(PurchaseOrder)
class POAdmin(admin.ModelAdmin):
    list_display = ("po_number", "supplier", "created_at", "submission_date")
    search_fields = ("po_number","supplier__name")


