from django.urls import path

from . import views

app_name = "clients"

urlpatterns = [
    # Главная страница - перенаправляет в соответствующий dashboard
    path("", views.CustomLoginView.as_view(), name="home"),
    # Общий dashboard
    path("dashboard/", views.dashboard_redirect_view, name="dashboard"),
    # Страница клиентов
    path("clients/", views.clients_list_view, name="clients_list"),
    # Dashboard'ы для разных ролей
    path(
        "parent/dashboard/",
        views.ParentDashboardView.as_view(),
        name="parent_dashboard",
    ),
    path(
        "child/dashboard/", views.ChildDashboardView.as_view(), name="child_dashboard"
    ),
    path(
        "teacher/dashboard/",
        views.TeacherDashboardView.as_view(),
        name="teacher_dashboard",
    ),
    # Уведомления
    path("notifications/", views.notifications_view, name="notifications"),
    path(
        "notifications/<int:notification_id>/read/",
        views.mark_notification_read,
        name="mark_notification_read",
    ),
    path(
        "notifications/<int:notification_id>/acknowledge/",
        views.acknowledge_notification,
        name="acknowledge_notification",
    ),
    # Профили
    path("profile/", views.profile_view, name="profile"),
    path("profile/edit/", views.edit_profile_view, name="edit_profile"),
    # Дети (для родителей)
    path("children/", views.children_list_view, name="children_list"),
    path("children/<int:child_id>/", views.child_detail_view, name="child_detail"),
    path(
        "children/<int:child_id>/schedule/",
        views.child_schedule_view,
        name="child_schedule",
    ),
    path(
        "children/<int:child_id>/attendance/",
        views.child_attendance_view,
        name="child_attendance",
    ),
]
