from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .views import (
    EVSULoginView,
    DashboardView,
    PRListView,
    PRWorkflowView,
    PRCreateView,
    assign_pr_number,
    pr_detail,
    RFQListView,
    RFQPreviewView,
    create_rfq,
    create_apr,
    AOQListView,
    AOQDetailView,
    create_aoq,
    generate_po_from_aoq,
    PODetailView,
    SupplierListView,
    SupplierCreateView,
)

app_name = "procurement"

urlpatterns = [
    # ----------------------------
    # Dashboard (Role-Based)
    # ----------------------------
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    
    # ----------------------------
    # Purchase Requests (PR)
    # ----------------------------
    path("prs/<int:pk>/submit/", views.submit_pr_for_verification, name="submit_pr"),
    path("prs/", PRListView.as_view(), name="pr_list"),
    path("prs/new/", PRCreateView.as_view(), name="pr_create"),
    path("prs/<int:pk>/", pr_detail, name="pr_detail"),
    path("prs/<int:pk>/workflow/", PRWorkflowView.as_view(), name="pr_workflow"),
    path('prs/<int:pk>/assign/', views.assign_pr_number, name='assign_pr_number'),
    path("prs/<int:pk>/edit/", views.PRUpdateView.as_view(), name="pr_edit"),
    
    # ----------------------------
    # Requests for Quotation (RFQ)
    # ----------------------------
    path("rfqs/", RFQListView.as_view(), name="rfq_list"),
    path("rfqs/<int:pk>/preview/", RFQPreviewView.as_view(), name="rfq_preview"),
    path("prs/<int:pr_id>/create_rfq/", create_rfq, name="create_rfq"),

    # ----------------------------
    # Agency Procurement Requests (APR)
    # ----------------------------
    path("prs/<int:pr_id>/create_apr/", create_apr, name="create_apr"),

    # ----------------------------
    # Abstract of Quotation (AOQ)
    # ----------------------------
    path("aoqs/", AOQListView.as_view(), name="aoq_list"),
    path("rfqs/<int:rfq_id>/create_aoq/", create_aoq, name="create_aoq"),
    path("aoqs/<int:pk>/", AOQDetailView.as_view(), name="aoq_detail"),
    path("aoqs/<int:pk>/generate_po/", generate_po_from_aoq, name="aoq_generate_po"),

    # ----------------------------
    # Purchase Orders (PO)
    # ----------------------------
    path("pos/<int:pk>/", PODetailView.as_view(), name="po_detail"),

    # ----------------------------
    # Supplier Management
    # ----------------------------
    path("suppliers/", SupplierListView.as_view(), name="supplier_list"),
    path("suppliers/new/", SupplierCreateView.as_view(), name="supplier_create"),

    # ----------------------------
    # Login
    # ----------------------------
    path("accounts/login/", EVSULoginView.as_view(), name="login"),
]
