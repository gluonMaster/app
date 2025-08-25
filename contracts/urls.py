from django.urls import path

from . import views

app_name = "contracts"

urlpatterns = [
    # Контракты
    path("", views.contracts_list_view, name="contracts_list"),
    path("<int:contract_id>/", views.contract_detail_view, name="contract_detail"),
    path("<int:contract_id>/items/", views.contract_items_view, name="contract_items"),
    # Заявки на изменение контрактов
    path("requests/", views.contract_requests_list_view, name="requests_list"),
    path("requests/create/", views.create_contract_request, name="create_request"),
    path(
        "requests/<int:request_id>/",
        views.contract_request_detail,
        name="request_detail",
    ),
    # AJAX endpoints
    path(
        "ajax/calculate-price/",
        views.calculate_price_estimate,
        name="calculate_price_estimate",
    ),
    path(
        "ajax/get-child-subjects/", views.get_child_subjects, name="get_child_subjects"
    ),
    # Счета и платежи (для родителей)
    path("invoices/", views.invoices_list_view, name="invoices_list"),
    path(
        "invoices/<int:invoice_id>/", views.invoice_detail_view, name="invoice_detail"
    ),
    path("payments/", views.payments_list_view, name="payments_list"),
    # Разовые начисления
    path("charges/", views.one_time_charges_view, name="one_time_charges"),
]
