from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    # Главная страница уведомлений
    path("", views.notifications_index_view, name="notifications_index"),
    # API для уведомлений
    path("api/unread-count/", views.unread_notifications_count, name="unread_count"),
    path("api/latest/", views.latest_notifications, name="latest_notifications"),
    path("api/mark-all-read/", views.mark_all_read, name="mark_all_read"),
    # Детали уведомления
    path("<int:notification_id>/", views.notification_detail, name="detail"),
    path(
        "<int:notification_id>/acknowledge/",
        views.acknowledge_notification,
        name="acknowledge",
    ),
    # Для администраторов
    path("admin/stats/", views.notification_stats_view, name="admin_stats"),
    path("admin/send/", views.send_notification_view, name="send_notification"),
    path("admin/bulk-send/", views.bulk_send_notifications, name="bulk_send"),
    path("admin/management/", views.notification_management, name="management"),
    path(
        "admin/<int:notification_id>/delete/", views.delete_notification, name="delete"
    ),
    path(
        "admin/<int:notification_id>/remind/", views.send_reminder, name="send_reminder"
    ),
    # Настройки пользователя
    path("settings/", views.user_notification_settings, name="user_settings"),
]
