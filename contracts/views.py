from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from clients.models import Child
from lessons.models import Subject
from notifications.models import notify_new_contract_request

from .forms import ContractChangeRequestForm, OneTimeChargeForm
from .models import (
    Contract,
    ContractChangeRequest,
    ContractItem,
    Invoice,
    OneTimeCharge,
)


@login_required
def create_contract_request(request):
    """Создание заявки на изменение контракта"""
    if not request.user.userprofile.is_parent:
        messages.error(request, "Zugriff verweigert.")
        return redirect("login")

    if request.method == "POST":
        form = ContractChangeRequestForm(request.POST, parent=request.user)
        if form.is_valid():
            request_obj = form.save(commit=False)
            request_obj.parent = request.user

            # Рассчитываем предполагаемое изменение стоимости
            request_obj.calculate_estimated_change()
            request_obj.save()

            # Уведомляем администраторов
            notify_new_contract_request(request_obj)

            messages.success(request, "Ihr Antrag wurde erfolgreich eingereicht.")
            return redirect("clients:parent_dashboard")
    else:
        form = ContractChangeRequestForm(parent=request.user)

    context = {"form": form, "title": "Vertragsänderung beantragen"}

    return render(request, "contracts/create_request.html", context)


@login_required
def contract_request_detail(request, request_id):
    """Детали заявки на изменение контракта"""
    contract_request = get_object_or_404(ContractChangeRequest, id=request_id)

    # Проверяем права доступа
    if (
        contract_request.parent != request.user
        and not request.user.userprofile.role in ["admin", "accountant"]
    ):
        messages.error(request, "Zugriff verweigert.")
        return redirect("login")

    context = {
        "contract_request": contract_request,
    }

    return render(request, "contracts/request_detail.html", context)


@login_required
def calculate_price_estimate(request):
    """AJAX endpoint для расчета предполагаемой стоимости"""
    if not request.user.userprofile.is_parent:
        return JsonResponse({"error": "Zugriff verweigert"}, status=403)

    request_type = request.GET.get("request_type")
    subject_id = request.GET.get("subject_id")
    child_id = request.GET.get("child_id")

    try:
        if request_type == "add_subject" and subject_id:
            from lessons.models import Subject

            subject = Subject.objects.get(id=subject_id)
            current_price = subject.current_price

            if current_price:
                # Упрощенный расчет - здесь можно добавить логику скидок
                estimated_change = float(current_price)
                return JsonResponse(
                    {
                        "estimated_change": estimated_change,
                        "formatted_change": f"+{estimated_change:.2f}€",
                    }
                )

        elif request_type == "remove_subject" and subject_id and child_id:
            from clients.models import Child

            child = Child.objects.get(id=child_id, parent=request.user)

            # Найти существующую позицию контракта
            contract_item = ContractItem.objects.filter(
                child=child, subject_id=subject_id, is_active=True
            ).first()

            if contract_item:
                estimated_change = -float(contract_item.final_price)
                return JsonResponse(
                    {
                        "estimated_change": estimated_change,
                        "formatted_change": f"{estimated_change:.2f}€",
                    }
                )

        return JsonResponse({"estimated_change": 0, "formatted_change": "0.00€"})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@login_required
def contracts_list_view(request):
    """Список контрактов для родителей"""
    if not request.user.userprofile.is_parent:
        messages.error(request, "Zugriff verweigert.")
        return redirect("login")

    contracts = Contract.objects.filter(parent=request.user).order_by("-created_at")

    context = {"contracts": contracts, "title": "Meine Verträge"}

    return render(request, "contracts/contracts_list.html", context)


@login_required
def contract_detail_view(request, contract_id):
    """Детальная страница контракта"""
    contract = get_object_or_404(Contract, id=contract_id)

    # Проверяем права доступа
    if contract.parent != request.user and not request.user.userprofile.role in [
        "admin",
        "accountant",
    ]:
        messages.error(request, "Zugriff verweigert.")
        return redirect("login")

    # Получаем позиции контракта
    contract_items = contract.items.filter(is_active=True).select_related(
        "child__user", "subject"
    )

    # Получаем связанные заявки
    change_requests = contract.change_requests.order_by("-created_at")[:10]

    context = {
        "contract": contract,
        "contract_items": contract_items,
        "change_requests": change_requests,
        "title": f"Vertrag {contract.contract_number}",
    }

    return render(request, "contracts/contract_detail.html", context)


@login_required
def contract_items_view(request, contract_id):
    """Список позиций контракта с возможностью управления"""
    contract = get_object_or_404(Contract, id=contract_id, parent=request.user)

    contract_items = contract.items.select_related("child__user", "subject").order_by(
        "child__user__first_name"
    )

    context = {
        "contract": contract,
        "contract_items": contract_items,
        "title": f"Vertragspositionen - {contract.contract_number}",
    }

    return render(request, "contracts/contract_items.html", context)


@login_required
def contract_requests_list_view(request):
    """Список заявок на изменение контрактов"""
    if not request.user.userprofile.is_parent:
        messages.error(request, "Zugriff verweigert.")
        return redirect("login")

    requests = ContractChangeRequest.objects.filter(parent=request.user).order_by(
        "-created_at"
    )

    context = {"requests": requests, "title": "Meine Anträge"}

    return render(request, "contracts/requests_list.html", context)


@login_required
def get_child_subjects(request):
    """AJAX endpoint для получения предметов ребенка"""
    if not request.user.userprofile.is_parent:
        return JsonResponse({"error": "Zugriff verweigert"}, status=403)

    child_id = request.GET.get("child_id")

    try:
        child = Child.objects.get(id=child_id, parent=request.user)

        # Получаем активные предметы ребенка
        current_subjects = ContractItem.objects.filter(
            child=child, is_active=True
        ).values_list("subject_id", "subject__name")

        # Получаем доступные предметы для добавления
        available_subjects = (
            Subject.objects.filter(is_active=True)
            .exclude(id__in=[s[0] for s in current_subjects])
            .values_list("id", "name")
        )

        return JsonResponse(
            {
                "current_subjects": list(current_subjects),
                "available_subjects": list(available_subjects),
            }
        )

    except Child.DoesNotExist:
        return JsonResponse({"error": "Kind nicht gefunden"}, status=404)


@login_required
def invoices_list_view(request):
    """Список счетов для родителей"""
    if not request.user.userprofile.is_parent:
        messages.error(request, "Zugriff verweigert.")
        return redirect("login")

    invoices = Invoice.objects.filter(parent=request.user).order_by("-issue_date")

    # Фильтрация по статусу
    status_filter = request.GET.get("status")
    if status_filter:
        invoices = invoices.filter(status=status_filter)

    context = {
        "invoices": invoices,
        "status_filter": status_filter,
        "invoice_statuses": Invoice.INVOICE_STATUS,
        "title": "Meine Rechnungen",
    }

    return render(request, "contracts/invoices_list.html", context)


@login_required
def invoice_detail_view(request, invoice_id):
    """Детальная страница счета"""
    invoice = get_object_or_404(Invoice, id=invoice_id)

    # Проверяем права доступа
    if invoice.parent != request.user and not request.user.userprofile.role in [
        "admin",
        "accountant",
    ]:
        messages.error(request, "Zugriff verweigert.")
        return redirect("login")

    # Получаем позиции счета
    invoice_items = invoice.items.select_related("child__user", "subject")

    # Получаем платежи
    payments = invoice.payments.order_by("-payment_date")

    context = {
        "invoice": invoice,
        "invoice_items": invoice_items,
        "payments": payments,
        "title": f"Rechnung {invoice.invoice_number}",
    }

    return render(request, "contracts/invoice_detail.html", context)


@login_required
def payments_list_view(request):
    """История платежей для родителей"""
    if not request.user.userprofile.is_parent:
        messages.error(request, "Zugriff verweigert.")
        return redirect("login")

    from .models import Payment

    payments = (
        Payment.objects.filter(invoice__parent=request.user)
        .select_related("invoice")
        .order_by("-payment_date")
    )

    context = {"payments": payments, "title": "Meine Zahlungen"}

    return render(request, "contracts/payments_list.html", context)


@login_required
def one_time_charges_view(request):
    """Разовые начисления для родителей"""
    if not request.user.userprofile.is_parent:
        messages.error(request, "Zugriff verweigert.")
        return redirect("login")

    charges = OneTimeCharge.objects.filter(parent=request.user).order_by("-charge_date")

    context = {"charges": charges, "title": "Einmalige Gebühren"}

    return render(request, "contracts/one_time_charges.html", context)
