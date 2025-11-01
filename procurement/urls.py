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
    PRDetailView,
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
    UnassignedPRListView,
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
    path("prs/<int:pk>/", views.PRDetailView.as_view(), name="pr_detail"),
    path("prs/<int:pk>/workflow/", PRWorkflowView.as_view(), name="pr_workflow"),
    path('prs/<int:pk>/assign/', views.assign_pr_number, name='assign_pr_number'),
    path("prs/<int:pk>/edit/", views.PRUpdateView.as_view(), name="pr_edit"),
    path("prs/<int:pk>/preview/", views.pr_preview, name="pr_preview"),
    path('prs/unassigned/', UnassignedPRListView.as_view(), name='unassigned_pr_list'),
    path("update_mode_ajax/<int:pk>/", views.update_mode_ajax, name="update_mode_ajax"),
    path("dashboard/requisitioner/", views.requisitioner_dashboard, name="dashboard_requisitioner"),
    path('update_status_ajax/<int:pk>/', views.update_status_ajax, name='update_pr_status'),
    path("signatories/", views.SignatoryListView.as_view(), name="signatory_list"),
    path("signatories/add/", views.SignatoryCreateView.as_view(), name="signatory_create"),
    path("signatories/add/ajax/", views.signatory_add_ajax, name="signatory_add_ajax"),
    path("signatories/<int:pk>/edit/view/", views.SignatoryUpdateView.as_view(), name="signatory_edit"),
    path("signatories/<int:pk>/delete/view/", views.SignatoryDeleteView.as_view(), name="signatory_delete"),
    # AJAX endpoints used by your JS:
    path("signatories/<int:pk>/edit/", views.signatory_edit_ajax, name="signatory_edit_ajax"),
    path("signatories/<int:pk>/delete/", views.signatory_delete_ajax, name="signatory_delete_ajax"),

    # ----------------------------
    # Requests for Quotation (RFQ)
    # ----------------------------
    path("rfqs/", RFQListView.as_view(), name="rfq_list"),
    path("rfqs/<int:pk>/preview/", RFQPreviewView.as_view(), name="rfq_preview"),
    path("prs/<int:pr_id>/create_rfq/", create_rfq, name="create_rfq"),
    # RFQ processing routes
    path("rfqs/<int:pk>/process/", views.rfq_process, name="rfq_process"),
    path("prs/<int:rfq_id>/add_bid/", views.add_bid, name="add_bid"),
    path("bids/<int:bid_id>/edit/", views.edit_bid, name="edit_bid"),
    path("bids/<int:bid_id>/remove/", views.remove_bid, name="remove_bid"),
    path("bids/<int:bid_id>/enter_lines/", views.enter_bid_lines, name="enter_bid_lines"),
    path("prs/<int:pr_id>/advance/", views.advance_pr_stage, name="advance_pr_stage"),
    path("rfqs/<int:rfq_id>/save_resolution/", views.save_resolution, name="save_resolution"),
    path("aoqs/<int:aoq_id>/award/", views.award_aoq_view, name="award_aoq"),

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
    path("aoqs/", views.AOQListView.as_view(), name="aoq_list"),
    
    # ----------------------------
    # Purchase Orders (PO)
    # ----------------------------
    path("pos/<int:pk>/", PODetailView.as_view(), name="po_detail"),
    path("pos/", views.POListView.as_view(), name="po_list"),

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
