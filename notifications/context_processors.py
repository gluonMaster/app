from .models import Notification


def notifications_context(request):
    """Контекст-процессор для уведомлений"""
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).count()

        critical_count = Notification.objects.filter(
            recipient=request.user,
            priority="critical",
            requires_acknowledgment=True,
            acknowledged_at__isnull=True,
        ).count()

        return {
            "unread_notifications_count": unread_count,
            "critical_notifications_count": critical_count,
        }

    return {
        "unread_notifications_count": 0,
        "critical_notifications_count": 0,
    }
