from django.contrib import admin
from django.db.models import Count, Sum
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from notifications.models import notify_contract_change, notify_contract_request_status

from .models import (
    Contract,
    ContractChangeRequest,
    ContractItem,
    ContractItemDiscount,
    Debt,
    Discount,
    DiscountType,
    Invoice,
    InvoiceItem,
    OneTimeCharge,
    Payment,
    PaymentPlan,
    PaymentPlanInstallment,
    PriceList,
)


class ContractItemInline(admin.TabularInline):
    """Инлайн для позиций контракта"""

    model = ContractItem
    extra = 0
    fields = (
        "child",
        "subject",
        "base_price",
        "final_price",
        "hours_per_month",
        "payer",
        "is_active",
    )
    readonly_fields = ("final_price",)


class ContractItemDiscountInline(admin.TabularInline):
    """Инлайн для скидок позиций контракта"""

    model = ContractItemDiscount
    extra = 0
    readonly_fields = ("applied_at", "applied_by")


@admin.register(PriceList)
class PriceListAdmin(admin.ModelAdmin):
    """Админка для прайс-листа"""

    list_display = (
        "subject",
        "price_per_hour",
        "valid_from",
        "valid_to",
        "is_active",
        "created_by",
    )
    list_filter = ("is_active", "valid_from", "subject")
    search_fields = ("subject__name", "subject__code")
    readonly_fields = ("created_at",)

    fieldsets = (
        (
            "Основная информация",
            {
                "fields": (
                    "subject",
                    "price_per_hour",
                    "valid_from",
                    "valid_to",
                    "is_active",
                )
            },
        ),
        (
            "Дополнительно",
            {"fields": ("notes", "created_by", "created_at"), "classes": ("collapse",)},
        ),
    )

    def save_model(self, request, obj, form, change):
        """Автоматически устанавливает создателя"""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(DiscountType)
class DiscountTypeAdmin(admin.ModelAdmin):
    """Админка для типов скидок"""

    list_display = ("name", "is_percentage", "is_active")
    list_filter = ("is_percentage", "is_active")
    search_fields = ("name", "description")


@admin.register(Discount)
class DiscountAdmin(admin.ModelAdmin):
    """Админка для скидок"""

    list_display = (
        "discount_type",
        "value",
        "get_value_display",
        "valid_from",
        "valid_to",
        "is_active",
    )
    list_filter = ("is_active", "discount_type", "valid_from")
    search_fields = ("condition_description",)

    fieldsets = (
        (
            "Основная информация",
            {
                "fields": (
                    "discount_type",
                    "condition_description",
                    "value",
                    "valid_from",
                    "valid_to",
                    "is_active",
                )
            },
        ),
        (
            "Условия применения",
            {
                "fields": ("min_subjects", "max_subjects", "applies_to_family"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_value_display(self, obj):
        """Отображает значение скидки с символом"""
        symbol = "%" if obj.discount_type.is_percentage else "€"
        return f"{obj.value}{symbol}"

    get_value_display.short_description = "Wert"


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    """Админка для контрактов"""

    list_display = (
        "contract_number",
        "parent",
        "contract_type",
        "payment_type",
        "status",
        "get_monthly_total",
        "start_date",
        "end_date",
    )
    list_filter = ("contract_type", "payment_type", "status", "start_date")
    search_fields = ("contract_number", "parent__first_name", "parent__last_name")
    readonly_fields = ("created_at", "updated_at", "total_monthly_amount")
    inlines = [ContractItemInline]

    fieldsets = (
        (
            "Основная информация",
            {
                "fields": (
                    "contract_number",
                    "parent",
                    "contract_type",
                    "payment_type",
                    "status",
                )
            },
        ),
        ("Даты", {"fields": ("start_date", "end_date", "cancellation_deadline")}),
        (
            "Файлы и заметки",
            {"fields": ("contract_file", "notes"), "classes": ("collapse",)},
        ),
        (
            "Системная информация",
            {
                "fields": (
                    "total_monthly_amount",
                    "created_at",
                    "created_by",
                    "updated_at",
                    "updated_by",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def get_monthly_total(self, obj):
        """Получает общую ежемесячную сумму"""
        try:
            total = obj.total_monthly_amount()
            if total is not None:
                # Безопасное преобразование в float
                total_amount = float(total)
                # Цветовое кодирование по типу оплаты
                if obj.payment_type == "sepa":
                    return format_html(
                        '<span style="color: green;">{:.2f}€</span>', total_amount
                    )
                elif obj.payment_type == "jobcenter":
                    return format_html(
                        '<span style="color: blue;">{:.2f}€</span>', total_amount
                    )
                else:
                    return f"{total_amount:.2f}€"
            return "0.00€"
        except (ValueError, TypeError, AttributeError):
            return "0.00€"

    get_monthly_total.short_description = "Monatssumme"

    def save_model(self, request, obj, form, change):
        """Автоматически устанавливает пользователя"""
        if not change:
            obj.created_by = request.user
        else:
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)

        # Уведомляем при изменениях
        if change:
            notify_contract_change(obj, "Vertrag wurde aktualisiert", request.user)


@admin.register(ContractItem)
class ContractItemAdmin(admin.ModelAdmin):
    """Админка для позиций контракта"""

    list_display = (
        "contract",
        "child",
        "subject",
        "base_price",
        "final_price",
        "payer",
        "is_active",
    )
    list_filter = ("payer", "is_active", "subject")
    search_fields = (
        "contract__contract_number",
        "child__user__first_name",
        "subject__name",
    )
    inlines = [ContractItemDiscountInline]

    actions = ["recalculate_prices", "activate_items", "deactivate_items"]

    def recalculate_prices(self, request, queryset):
        """Пересчитывает цены с учетом скидок"""
        updated = 0
        for item in queryset:
            item.update_final_price()
            updated += 1
        self.message_user(request, f"{updated} Positionen wurden neu berechnet.")

    recalculate_prices.short_description = "Preise neu berechnen"

    def activate_items(self, request, queryset):
        """Активирует позиции"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} Positionen wurden aktiviert.")

    activate_items.short_description = "Positionen aktivieren"

    def deactivate_items(self, request, queryset):
        """Деактивирует позиции"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} Positionen wurden deaktiviert.")

    deactivate_items.short_description = "Positionen deaktivieren"


@admin.register(ContractChangeRequest)
class ContractChangeRequestAdmin(admin.ModelAdmin):
    """Админка для заявок на изменение контрактов"""

    list_display = (
        "parent",
        "child",
        "request_type",
        "subject",
        "status",
        "estimated_monthly_change",
        "created_at",
    )
    list_filter = ("request_type", "status", "created_at")
    search_fields = ("parent__first_name", "parent__last_name", "description")
    readonly_fields = ("created_at", "updated_at", "estimated_monthly_change")

    fieldsets = (
        (
            "Основная информация",
            {"fields": ("parent", "child", "contract", "request_type", "status")},
        ),
        (
            "Детали заявки",
            {
                "fields": (
                    "subject",
                    "requested_start_date",
                    "requested_end_date",
                    "description",
                    "parent_reason",
                )
            },
        ),
        (
            "Финансовый расчет",
            {"fields": ("estimated_monthly_change",), "classes": ("collapse",)},
        ),
        (
            "Обработка администратором",
            {
                "fields": (
                    "processed_by",
                    "processed_at",
                    "admin_notes",
                    "rejection_reason",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Системная информация",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    actions = ["approve_requests", "reject_requests"]

    def approve_requests(self, request, queryset):
        """Утверждает заявки"""
        updated = 0
        for req in queryset.filter(status="pending"):
            req.status = "approved"
            req.processed_by = request.user
            req.save()
            notify_contract_request_status(req, request.user)
            updated += 1
        self.message_user(request, f"{updated} Antraege wurden genehmigt.")

    approve_requests.short_description = "Ausgewaehlte Antraege genehmigen"

    def reject_requests(self, request, queryset):
        """Отклоняет заявки"""
        updated = 0
        for req in queryset.filter(status="pending"):
            req.status = "rejected"
            req.processed_by = request.user
            req.rejection_reason = (
                req.rejection_reason or "Abgelehnt durch Administrator"
            )
            req.save()
            notify_contract_request_status(req, request.user)
            updated += 1
        self.message_user(request, f"{updated} Antraege wurden abgelehnt.")

    reject_requests.short_description = "Ausgewaehlte Antraege ablehnen"


@admin.register(OneTimeCharge)
class OneTimeChargeAdmin(admin.ModelAdmin):
    """Админка для разовых начислений"""

    list_display = (
        "parent",
        "child",
        "charge_type",
        "description",
        "amount",
        "charge_date",
        "due_date",
        "is_paid",
    )
    list_filter = ("charge_type", "is_paid", "charge_date")
    search_fields = ("parent__first_name", "parent__last_name", "description")
    readonly_fields = ("created_at",)

    fieldsets = (
        (
            "Основная информация",
            {"fields": ("parent", "child", "charge_type", "description", "amount")},
        ),
        ("Даты", {"fields": ("charge_date", "due_date", "is_paid", "paid_date")}),
        (
            "Дополнительно",
            {"fields": ("notes", "created_by", "created_at"), "classes": ("collapse",)},
        ),
    )

    actions = ["mark_as_paid"]

    def mark_as_paid(self, request, queryset):
        """Отмечает как оплаченное"""
        from datetime import date

        updated = queryset.update(is_paid=True, paid_date=date.today())
        self.message_user(request, f"{updated} Gebuehren wurden als bezahlt markiert.")

    mark_as_paid.short_description = "Als bezahlt markieren"


# Финансовые модели


class InvoiceItemInline(admin.TabularInline):
    """Инлайн для позиций счета"""

    model = InvoiceItem
    extra = 0
    readonly_fields = ("total_amount",)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """Админка для счетов"""

    list_display = (
        "invoice_number",
        "parent",
        "period_start",
        "period_end",
        "total_amount",
        "status",
        "issue_date",
        "due_date",
    )
    list_filter = ("status", "issue_date", "due_date")
    search_fields = ("invoice_number", "parent__first_name", "parent__last_name")
    readonly_fields = ("created_at", "subtotal", "total_discount", "total_amount")
    inlines = [InvoiceItemInline]

    fieldsets = (
        (
            "Основная информация",
            {"fields": ("invoice_number", "parent", "period_start", "period_end")},
        ),
        (
            "Финансы",
            {"fields": ("subtotal", "total_discount", "total_amount", "status")},
        ),
        ("Даты", {"fields": ("issue_date", "due_date", "paid_date")}),
        (
            "Дополнительно",
            {
                "fields": ("invoice_file", "notes", "created_by", "created_at"),
                "classes": ("collapse",),
            },
        ),
    )

    actions = ["mark_as_sent", "mark_as_paid"]

    def mark_as_sent(self, request, queryset):
        """Отмечает счета как отправленные"""
        updated = queryset.update(status="sent")
        self.message_user(
            request, f"{updated} Rechnungen wurden als gesendet markiert."
        )

    mark_as_sent.short_description = "Als gesendet markieren"

    def mark_as_paid(self, request, queryset):
        """Отмечает счета как оплаченные"""
        from datetime import date

        updated = queryset.update(status="paid", paid_date=date.today())
        self.message_user(request, f"{updated} Rechnungen wurden als bezahlt markiert.")

    mark_as_paid.short_description = "Als bezahlt markieren"


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Админка для платежей"""

    list_display = ("invoice", "amount", "payment_method", "status", "payment_date")
    list_filter = ("payment_method", "status", "payment_date")
    search_fields = ("invoice__invoice_number", "reference_number")
    readonly_fields = ("created_at",)


@admin.register(Debt)
class DebtAdmin(admin.ModelAdmin):
    """Админка для задолженностей"""

    list_display = (
        "parent",
        "original_amount",
        "remaining_amount",
        "due_date",
        "get_days_overdue",
        "is_resolved",
    )
    list_filter = ("is_resolved", "due_date", "overdue_since")
    search_fields = ("parent__first_name", "parent__last_name")
    readonly_fields = ("created_at", "updated_at", "days_overdue")

    def get_days_overdue(self, obj):
        """Получает количество дней просрочки"""
        days = obj.days_overdue
        if days > 0:
            if days > 30:
                return format_html(
                    '<span style="color: red; font-weight: bold;">{} Tage</span>', days
                )
            elif days > 7:
                return format_html('<span style="color: orange;">{} Tage</span>', days)
            else:
                return format_html('<span style="color: #ff6600;">{} Tage</span>', days)
        return "-"

    get_days_overdue.short_description = "Tage ueberfaellig"

    actions = ["mark_as_resolved"]

    def mark_as_resolved(self, request, queryset):
        """Отмечает задолженности как погашенные"""
        updated = 0
        for debt in queryset:
            debt.mark_as_resolved()
            updated += 1
        self.message_user(request, f"{updated} Schulden wurden als beglichen markiert.")

    mark_as_resolved.short_description = "Als beglichen markieren"


class PaymentPlanInstallmentInline(admin.TabularInline):
    """Инлайн для рассрочки"""

    model = PaymentPlanInstallment
    extra = 0
    readonly_fields = ("installment_number",)


@admin.register(PaymentPlan)
class PaymentPlanAdmin(admin.ModelAdmin):
    """Админка для планов погашения"""

    list_display = (
        "debt",
        "total_amount",
        "monthly_payment",
        "start_date",
        "end_date",
        "is_active",
    )
    list_filter = ("is_active", "start_date")
    search_fields = ("debt__parent__first_name", "debt__parent__last_name")
    inlines = [PaymentPlanInstallmentInline]
