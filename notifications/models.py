from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Notification(models.Model):
    """Модель уведомлений"""

    NOTIFICATION_TYPES = [
        ("contract_change", "Vertragsaenderung"),  # Изменение контракта
        ("price_change", "Preisaenderung"),  # Изменение цен
        ("schedule_change", "Stundenplanaenderung"),  # Изменение расписания
        ("discount_change", "Rabattaenderung"),  # Изменение скидок
        ("sepa_important", "SEPA Wichtig"),  # Важное для SEPA клиентов
        ("absence_alert", "Fehlzeiten-Benachrichtigung"),  # Уведомление о пропусках
        ("payment_reminder", "Zahlungserinnerung"),  # Напоминание об оплате
        ("request_status", "Antragsstatus"),  # Статус заявки
        ("general", "Allgemeine Mitteilung"),  # Общее уведомление
    ]

    PRIORITY_LEVELS = [
        ("low", "Niedrig"),
        ("normal", "Normal"),
        ("high", "Hoch"),
        ("critical", "Kritisch"),  # Для SEPA клиентов при изменениях
    ]

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Empfaenger",
    )
    notification_type = models.CharField(
        max_length=20, choices=NOTIFICATION_TYPES, verbose_name="Benachrichtigungstyp"
    )
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_LEVELS,
        default="normal",
        verbose_name="Prioritaet",
    )
    title = models.CharField(max_length=200, verbose_name="Titel")
    message = models.TextField(verbose_name="Nachricht")

    is_read = models.BooleanField(default=False, verbose_name="Gelesen")
    is_important = models.BooleanField(default=False, verbose_name="Wichtig")
    requires_acknowledgment = models.BooleanField(
        default=False, verbose_name="Bestaetigung erforderlich"
    )  # Для критичных уведомлений
    acknowledged_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Bestaetigt am"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    read_at = models.DateTimeField(null=True, blank=True, verbose_name="Gelesen am")

    # Связь с объектом, вызвавшим уведомление
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    class Meta:
        verbose_name = "Benachrichtigung"
        verbose_name_plural = "Benachrichtigungen"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read"]),
            models.Index(fields=["notification_type"]),
            models.Index(fields=["priority"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.recipient.get_full_name()}"

    def mark_as_read(self):
        """Отмечает уведомление как прочитанное"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])

    def acknowledge(self):
        """Подтверждает получение критичного уведомления"""
        if self.requires_acknowledgment and not self.acknowledged_at:
            from django.utils import timezone

            self.acknowledged_at = timezone.now()
            self.save(update_fields=["acknowledged_at"])


class ChangeLog(models.Model):
    """Модель истории изменений (аудит)"""

    table_name = models.CharField(max_length=50, verbose_name="Tabellenname")
    record_id = models.IntegerField(verbose_name="Datensatz-ID")
    field_name = models.CharField(max_length=50, verbose_name="Feldname")
    old_value = models.TextField(blank=True, null=True, verbose_name="Alter Wert")
    new_value = models.TextField(blank=True, null=True, verbose_name="Neuer Wert")

    changed_by = models.ForeignKey(
        User, on_delete=models.PROTECT, verbose_name="Geaendert von"
    )
    changed_at = models.DateTimeField(auto_now_add=True, verbose_name="Geaendert am")
    change_reason = models.TextField(blank=True, verbose_name="Aenderungsgrund")

    class Meta:
        verbose_name = "Aenderungsprotokoll"
        verbose_name_plural = "Aenderungsprotokolle"
        ordering = ["-changed_at"]
        indexes = [
            models.Index(fields=["table_name", "record_id"]),
            models.Index(fields=["changed_by"]),
        ]

    def __str__(self):
        return f"{self.table_name}#{self.record_id} - {self.field_name}"


# Utility functions for notifications
def notify_contract_change(contract, change_description, changed_by):
    """
    Уведомляет всех заинтересованных при изменении контракта
    """
    from django.contrib.auth.models import User

    # Уведомляем клиента
    parent = contract.parent

    # Определяем приоритет для SEPA клиентов
    priority = "critical" if contract.payment_type == "sepa" else "high"
    requires_ack = contract.payment_type == "sepa"

    Notification.objects.create(
        recipient=parent,
        notification_type="contract_change",
        priority=priority,
        title=f"Vertragsaenderung - Vertrag {contract.contract_number}",
        message=f"Ihr Vertrag wurde geaendert: {change_description}",
        requires_acknowledgment=requires_ack,
        content_object=contract,
    )

    # Уведомляем всех бухгалтеров
    accountants = User.objects.filter(userprofile__role="accountant")
    for accountant in accountants:
        Notification.objects.create(
            recipient=accountant,
            notification_type="contract_change",
            priority="normal",
            title=f"Vertragsaenderung - {parent.get_full_name()}",
            message=f"Vertrag {contract.contract_number} wurde geaendert von {changed_by.get_full_name()}: {change_description}",
            content_object=contract,
        )


def notify_price_change(price_list, changed_by):
    """
    Уведомляет клиентов и бухгалтеров об изменении цен
    """
    from contracts.models import Contract

    # Находим всех клиентов, затронутых изменением цены
    affected_contracts = Contract.objects.filter(
        items__subject=price_list.subject, status="active"
    ).distinct()

    for contract in affected_contracts:
        parent = contract.parent
        priority = "critical" if contract.payment_type == "sepa" else "high"

        Notification.objects.create(
            recipient=parent,
            notification_type="price_change",
            priority=priority,
            title=f"Preisaenderung - {price_list.subject.name}",
            message=f"Der Preis fuer {price_list.subject.name} wurde auf {price_list.price_per_hour}€ pro Stunde geaendert, gueltig ab {price_list.valid_from}",
            requires_acknowledgment=(priority == "critical"),
            content_object=price_list,
        )

    # Уведомляем бухгалтеров
    from django.contrib.auth.models import User

    accountants = User.objects.filter(userprofile__role="accountant")
    for accountant in accountants:
        Notification.objects.create(
            recipient=accountant,
            notification_type="price_change",
            priority="normal",
            title=f"Preisaenderung - {price_list.subject.name}",
            message=f"Neuer Preis: {price_list.price_per_hour}€/Std., {len(affected_contracts)} Vertraege betroffen",
            content_object=price_list,
        )


def notify_absence(absence_record):
    """
    Уведомляет родителей о пропуске ребенка
    """
    child = absence_record.child
    parent = child.parent

    Notification.objects.create(
        recipient=parent,
        notification_type="absence_alert",
        priority="normal",
        title=f"Fehlzeit - {child.user.get_full_name()}",
        message=f"Ihr Kind {child.user.get_full_name()} war nicht im Unterricht {absence_record.subject.name} am {absence_record.lesson_date.strftime('%d.%m.%Y')}",
        content_object=absence_record,
    )

    # Также уведомляем самого ребенка, если у него есть аккаунт
    if child.user.is_active:
        Notification.objects.create(
            recipient=child.user,
            notification_type="absence_alert",
            priority="normal",
            title=f"Fehlzeit - {absence_record.subject.name}",
            message=f"Du warst nicht im Unterricht {absence_record.subject.name} am {absence_record.lesson_date.strftime('%d.%m.%Y')}",
            content_object=absence_record,
        )


def notify_contract_request_status(request, processed_by):
    """
    Уведомляет о статусе заявки на изменение контракта
    """
    parent = request.parent

    if request.status == "approved":
        title = f"Antrag genehmigt - {request.get_request_type_display()}"
        message = f"Ihr Antrag wurde genehmigt: {request.description}"
        priority = "normal"
    elif request.status == "rejected":
        title = f"Antrag abgelehnt - {request.get_request_type_display()}"
        message = f"Ihr Antrag wurde abgelehnt: {request.rejection_reason}"
        priority = "high"
    else:
        title = f"Antragsstatus geaendert - {request.get_request_type_display()}"
        message = f"Status Ihres Antrags: {request.get_status_display()}"
        priority = "normal"

    # Уведомляем родителя
    Notification.objects.create(
        recipient=parent,
        notification_type="request_status",
        priority=priority,
        title=title,
        message=message,
        content_object=request,
    )

    # Уведомляем бухгалтеров о принятых заявках
    if request.status == "approved":
        from django.contrib.auth.models import User

        accountants = User.objects.filter(userprofile__role="accountant")
        for accountant in accountants:
            Notification.objects.create(
                recipient=accountant,
                notification_type="request_status",
                priority="normal",
                title=f"Antrag genehmigt - {parent.get_full_name()}",
                message=f"Antrag von {parent.get_full_name()} wurde genehmigt von {processed_by.get_full_name()}: {request.description}",
                content_object=request,
            )


def notify_new_contract_request(request):
    """
    Уведомляет администраторов о новой заявке на изменение контракта
    """
    from django.contrib.auth.models import User

    # Уведомляем всех администраторов
    admins = User.objects.filter(userprofile__role__in=["admin", "accountant"])

    for admin in admins:
        Notification.objects.create(
            recipient=admin,
            notification_type="request_status",
            priority="high",
            title=f"Neuer Antrag - {request.get_request_type_display()}",
            message=f"Neuer Antrag von {request.parent.get_full_name()}: {request.description}",
            content_object=request,
        )


def notify_schedule_change(group, change_description, changed_by):
    """
    Уведомляет о изменении расписания группы
    """
    # Находим всех родителей детей в группе
    from lessons.models import GroupEnrollment

    enrollments = GroupEnrollment.objects.filter(
        group=group, status="active"
    ).select_related("child__parent")

    for enrollment in enrollments:
        parent = enrollment.child.parent

        Notification.objects.create(
            recipient=parent,
            notification_type="schedule_change",
            priority="high",
            title=f"Stundenplanaenderung - {group.name}",
            message=f"Der Stundenplan fuer die Gruppe {group.name} wurde geaendert: {change_description}",
            content_object=group,
        )

        # Также уведомляем детей
        child_user = enrollment.child.user
        if child_user.is_active:
            Notification.objects.create(
                recipient=child_user,
                notification_type="schedule_change",
                priority="high",
                title=f"Stundenplanaenderung - {group.name}",
                message=f"Der Stundenplan fuer deine Gruppe {group.name} wurde geaendert: {change_description}",
                content_object=group,
            )
