# notifications/views.py
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import SendNotificationForm
from .models import Notification


def is_admin_or_accountant(user):
    """Проверка, является ли пользователь администратором или бухгалтером"""
    return (
        user.is_authenticated
        and hasattr(user, "userprofile")
        and user.userprofile.role in ["admin", "accountant"]
    )


@login_required
def unread_notifications_count(request):
    """API endpoint для получения количества непрочитанных уведомлений"""
    count = Notification.objects.filter(recipient=request.user, is_read=False).count()

    critical_count = Notification.objects.filter(
        recipient=request.user,
        priority="critical",
        requires_acknowledgment=True,
        acknowledged_at__isnull=True,
    ).count()

    return JsonResponse({"unread_count": count, "critical_count": critical_count})


@login_required
def latest_notifications(request):
    """API endpoint для получения последних уведомлений"""
    notifications = Notification.objects.filter(recipient=request.user).order_by(
        "-created_at"
    )[:10]

    notifications_data = []
    for notification in notifications:
        notifications_data.append(
            {
                "id": notification.id,
                "title": notification.title,
                "message": (
                    notification.message[:100] + "..."
                    if len(notification.message) > 100
                    else notification.message
                ),
                "is_read": notification.is_read,
                "priority": notification.priority,
                "notification_type": notification.get_notification_type_display(),
                "created_at": notification.created_at.strftime("%d.%m.%Y %H:%M"),
                "requires_acknowledgment": notification.requires_acknowledgment,
                "acknowledged_at": (
                    notification.acknowledged_at.strftime("%d.%m.%Y %H:%M")
                    if notification.acknowledged_at
                    else None
                ),
            }
        )

    return JsonResponse({"notifications": notifications_data})


@login_required
@require_POST
def mark_all_read(request):
    """Отмечает все уведомления пользователя как прочитанные"""
    updated_count = Notification.objects.filter(
        recipient=request.user, is_read=False
    ).update(is_read=True, read_at=timezone.now())

    return JsonResponse({"success": True, "updated_count": updated_count})


@user_passes_test(is_admin_or_accountant)
def notification_stats_view(request):
    """Страница статистики уведомлений для администраторов"""
    # Общая статистика
    total_notifications = Notification.objects.count()
    unread_notifications = Notification.objects.filter(is_read=False).count()
    critical_unacknowledged = Notification.objects.filter(
        priority="critical", requires_acknowledgment=True, acknowledged_at__isnull=True
    ).count()

    # Статистика по типам
    type_stats = (
        Notification.objects.values("notification_type")
        .annotate(total=Count("id"), unread=Count("id", filter=Q(is_read=False)))
        .order_by("-total")
    )

    # Статистика по пользователям с наибольшим количеством непрочитанных
    user_stats = (
        Notification.objects.filter(is_read=False)
        .values(
            "recipient__first_name",
            "recipient__last_name",
            "recipient__userprofile__role",
        )
        .annotate(unread_count=Count("id"))
        .order_by("-unread_count")[:10]
    )

    # Статистика за последние 7 дней
    week_ago = datetime.now() - timedelta(days=7)
    recent_stats = []
    for i in range(7):
        day = week_ago + timedelta(days=i)
        day_count = Notification.objects.filter(created_at__date=day.date()).count()
        recent_stats.append({"date": day.strftime("%d.%m"), "count": day_count})

    # Критичные непрочитанные уведомления
    critical_notifications = (
        Notification.objects.filter(
            priority="critical",
            requires_acknowledgment=True,
            acknowledged_at__isnull=True,
        )
        .select_related("recipient", "recipient__userprofile")
        .order_by("-created_at")[:20]
    )

    context = {
        "title": "Benachrichtigungsstatistik",
        "total_notifications": total_notifications,
        "unread_notifications": unread_notifications,
        "critical_unacknowledged": critical_unacknowledged,
        "type_stats": type_stats,
        "user_stats": user_stats,
        "recent_stats": recent_stats,
        "critical_notifications": critical_notifications,
    }

    return render(request, "notifications/admin_stats.html", context)


@user_passes_test(is_admin_or_accountant)
def send_notification_view(request):
    """Страница для отправки уведомления администраторами"""
    if request.method == "POST":
        form = SendNotificationForm(request.POST)
        if form.is_valid():
            recipients = form.cleaned_data["recipients"]

            created_count = 0
            for recipient in recipients:
                Notification.objects.create(
                    recipient=recipient,
                    notification_type=form.cleaned_data["notification_type"],
                    priority=form.cleaned_data["priority"],
                    title=form.cleaned_data["title"],
                    message=form.cleaned_data["message"],
                    is_important=form.cleaned_data["is_important"],
                    requires_acknowledgment=form.cleaned_data[
                        "requires_acknowledgment"
                    ],
                )
                created_count += 1

            messages.success(
                request, f"Benachrichtigung an {created_count} Empfänger gesendet."
            )
            return redirect("notifications:send_notification")
    else:
        form = SendNotificationForm()

    context = {"form": form, "title": "Benachrichtigung senden"}

    return render(request, "notifications/send_notification.html", context)


@user_passes_test(is_admin_or_accountant)
def bulk_send_notifications(request):
    """Массовая отправка уведомлений по ролям"""
    if request.method == "POST":
        recipient_roles = request.POST.getlist("recipient_roles")
        notification_type = request.POST.get("notification_type")
        priority = request.POST.get("priority")
        title = request.POST.get("title")
        message = request.POST.get("message")
        is_important = request.POST.get("is_important") == "on"
        requires_acknowledgment = request.POST.get("requires_acknowledgment") == "on"

        if not all([recipient_roles, notification_type, title, message]):
            messages.error(request, "Bitte füllen Sie alle erforderlichen Felder aus.")
            return redirect("notifications:bulk_send")

        # Получаем пользователей по ролям
        recipients = User.objects.filter(
            userprofile__role__in=recipient_roles, is_active=True
        )

        created_count = 0
        for recipient in recipients:
            Notification.objects.create(
                recipient=recipient,
                notification_type=notification_type,
                priority=priority,
                title=title,
                message=message,
                is_important=is_important,
                requires_acknowledgment=requires_acknowledgment,
            )
            created_count += 1

        messages.success(
            request, f"Massenbenachrichtigung an {created_count} Empfänger gesendet."
        )
        return redirect("notifications:bulk_send")

    # GET request - показываем форму
    from clients.models import UserProfile

    context = {
        "title": "Massenbenachrichtigung senden",
        "notification_types": Notification.NOTIFICATION_TYPES,
        "priority_levels": Notification.PRIORITY_LEVELS,
        "user_roles": UserProfile.ROLE_CHOICES,
    }

    return render(request, "notifications/bulk_send.html", context)


@user_passes_test(is_admin_or_accountant)
def notification_management(request):
    """Страница управления уведомлениями для администраторов"""
    # Фильтры
    status_filter = request.GET.get("status", "all")
    type_filter = request.GET.get("type", "all")
    priority_filter = request.GET.get("priority", "all")

    notifications = Notification.objects.select_related(
        "recipient", "recipient__userprofile"
    )

    # Применяем фильтры
    if status_filter == "unread":
        notifications = notifications.filter(is_read=False)
    elif status_filter == "critical_unack":
        notifications = notifications.filter(
            priority="critical",
            requires_acknowledgment=True,
            acknowledged_at__isnull=True,
        )

    if type_filter != "all":
        notifications = notifications.filter(notification_type=type_filter)

    if priority_filter != "all":
        notifications = notifications.filter(priority=priority_filter)

    notifications = notifications.order_by("-created_at")

    # Пагинация
    from django.core.paginator import Paginator

    paginator = Paginator(notifications, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "title": "Benachrichtigungsverwaltung",
        "page_obj": page_obj,
        "status_filter": status_filter,
        "type_filter": type_filter,
        "priority_filter": priority_filter,
        "notification_types": Notification.NOTIFICATION_TYPES,
        "priority_levels": Notification.PRIORITY_LEVELS,
    }

    return render(request, "notifications/management.html", context)


@user_passes_test(is_admin_or_accountant)
@require_POST
def delete_notification(request, notification_id):
    """Удаление уведомления администратором"""
    notification = get_object_or_404(Notification, id=notification_id)

    recipient_name = notification.recipient.get_full_name()
    notification.delete()

    messages.success(request, f"Benachrichtigung für {recipient_name} wurde gelöscht.")
    return redirect("notifications:management")


@user_passes_test(is_admin_or_accountant)
@require_POST
def send_reminder(request, notification_id):
    """Отправка напоминания о критичном уведомлении"""
    original_notification = get_object_or_404(
        Notification,
        id=notification_id,
        priority="critical",
        requires_acknowledgment=True,
        acknowledged_at__isnull=True,
    )

    # Создаем напоминание
    Notification.objects.create(
        recipient=original_notification.recipient,
        notification_type="general",
        priority="critical",
        title=f"ERINNERUNG: {original_notification.title}",
        message=f"Sie haben eine wichtige Benachrichtigung noch nicht bestätigt:\n\n{original_notification.message}",
        requires_acknowledgment=True,
        content_object=original_notification.content_object,
    )

    messages.success(
        request,
        f"Erinnerung an {original_notification.recipient.get_full_name()} gesendet.",
    )
    return redirect("notifications:management")


@login_required
def notification_detail(request, notification_id):
    """Детальная страница уведомления"""
    notification = get_object_or_404(
        Notification, id=notification_id, recipient=request.user
    )

    # Отмечаем как прочитанное
    if not notification.is_read:
        notification.mark_as_read()

    context = {
        "notification": notification,
    }

    return render(request, "notifications/detail.html", context)


@login_required
def user_notification_settings(request):
    """Настройки уведомлений пользователя"""
    # TODO: Реализовать настройки уведомлений пользователя
    # Например, какие типы уведомлений получать, как часто и т.д.

    if request.method == "POST":
        # Обработка сохранения настроек
        messages.success(request, "Einstellungen gespeichert.")
        return redirect("notifications:user_settings")

    context = {
        "title": "Benachrichtigungseinstellungen",
    }

    return render(request, "notifications/user_settings.html", context)


@login_required
def notifications_index_view(request):
    """Главная страница уведомлений"""
    # Получаем уведомления пользователя
    notifications = Notification.objects.filter(recipient=request.user).order_by(
        "-created_at"
    )[:20]

    context = {
        "notifications": notifications,
        "title": "Уведомления",
    }
    return render(request, "notifications/notifications_index.html", context)
