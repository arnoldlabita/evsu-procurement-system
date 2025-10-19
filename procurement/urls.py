from django.urls import path
from . import views

app_name = "procurement"

urlpatterns = [
    # ----------------------------
    # Dashboard (Role-Based)
    # ----------------------------
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),

    # ----------------------------
    # Purchase Requests (PR)
    # ----------------------------
    path("prs/", views.PRListView.as_view(), name="pr_list"),
    path("prs/new/", views.PRCreateView.as_view(), name="pr_create"),
    path("prs/<int:pk>/", views.PRDetailView.as_view(), name="pr_detail"),
    path("prs/<int:pk>/assign_number/", views.assign_pr_number, name="pr_assign_number"),

    # ----------------------------
    # Requests for Quotation (RFQ)
    # ----------------------------
    path("rfqs/", views.RFQListView.as_view(), name="rfq_list"),  # ✅ RFQ list page
    path("rfqs/<int:pk>/preview/", views.RFQPreviewView.as_view(), name="rfq_preview"),
    path("prs/<int:pr_id>/create_rfq/", views.create_rfq, name="create_rfq"),

    # ----------------------------
    # Agency Procurement Requests (APR)
    # ----------------------------
    path("prs/<int:pr_id>/create_apr/", views.create_apr, name="create_apr"),

    # ----------------------------
    # Abstract of Quotation (AOQ)
    # ----------------------------
    path("aoqs/", views.AOQListView.as_view(), name="aoq_list"),  # ✅ AOQ list page
    path("rfqs/<int:rfq_id>/create_aoq/", views.create_aoq, name="create_aoq"),
    path("aoqs/<int:pk>/", views.AOQDetailView.as_view(), name="aoq_detail"),
    path("aoqs/<int:pk>/generate_po/", views.generate_po_from_aoq, name="aoq_generate_po"),

    # ----------------------------
    # Purchase Orders (PO)
    # ----------------------------
    path("pos/<int:pk>/", views.PODetailView.as_view(), name="po_detail"),

    # ----------------------------
    # Supplier Management
    # ----------------------------
    path("suppliers/", views.SupplierListView.as_view(), name="supplier_list"),
    path("suppliers/new/", views.SupplierCreateView.as_view(), name="supplier_create"),
]
