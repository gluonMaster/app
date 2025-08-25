from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def sum_amounts(queryset):
    """Суммирует поле amount в QuerySet"""
    total = Decimal("0.00")
    for item in queryset:
        if hasattr(item, "amount"):
            total += item.amount
    return total


@register.filter
def subtract(value, arg):
    """Вычитает arg из value"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return value


@register.filter
def calculate_hourly_rate(base_price, hours_per_month):
    """Рассчитывает почасовую стоимость"""
    try:
        if hours_per_month and hours_per_month > 0:
            return float(base_price) / float(hours_per_month)
        return 0
    except (ValueError, TypeError, ZeroDivisionError):
        return 0


@register.filter
def total_payments(payments):
    """Вычисляет общую сумму платежей"""
    total = Decimal("0.00")
    for payment in payments:
        if hasattr(payment, "amount"):
            total += payment.amount
    return total
