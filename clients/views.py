# clients/views.py
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView

from contracts.models import Contract, ContractChangeRequest, ContractItem
from lessons.models import (
    AbsenceHistory,
    ActualLesson,
    Group,
    GroupEnrollment,
    TrialLesson,
)
from notifications.models import Notification

from .forms import ChildForm, UserForm, UserProfileForm
from .models import Child, UserProfile


class CustomLoginView(auth_views.LoginView):
    """Кастомная страница входа с перенаправлением по ролям"""

    template_name = "registration/login.html"

    def get_success_url(self):
        """Перенаправляет пользователей в соответствующие кабинеты"""
        user = self.request.user
        if hasattr(user, "userprofile"):
            role = user.userprofile.role
            if role == "parent":
                return "/parent/dashboard/"
            elif role == "child":
                return "/child/dashboard/"
            elif role == "teacher":
                return "/teacher/dashboard/"
            elif role in ["admin", "accountant"]:
                return "/admin/"
        return "/dashboard/"


@method_decorator(login_required, name="dispatch")
class DashboardView(TemplateView):
    """Базовый класс для dashboard'ов"""

    def dispatch(self, request, *args, **kwargs):
        # Проверяем роль пользователя
        if not hasattr(request.user, "userprofile"):
            messages.error(request, "Ihr Profil ist nicht vollständig konfiguriert.")
            return redirect("/admin/")
        return super().dispatch(request, *args, **kwargs)


class ParentDashboardView(DashboardView):
    """Dashboard для родителей"""

    template_name = "clients/parent_dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.userprofile.is_parent:
            messages.error(request, "Zugriff verweigert.")
            return redirect("/login/")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Информация о детях
        children = (
            Child.objects.filter(parent=user, is_active=True)
            .select_related("user")
            .prefetch_related("groupenrollment_set__group__subject")
        )
        context["children"] = children

        # Активные контракты
        active_contracts = Contract.objects.filter(
            parent=user, status="active"
        ).prefetch_related("items__child", "items__subject")
        context["active_contracts"] = active_contracts

        # Общая ежемесячная сумма
        total_monthly = sum(
            contract.total_monthly_amount or 0 for contract in active_contracts
        )
        context["total_monthly_amount"] = total_monthly

        # Ожидающие заявки
        pending_requests = ContractChangeRequest.objects.filter(
            parent=user, status="pending"
        ).order_by("-created_at")
        context["pending_requests"] = pending_requests

        # Недавние уведомления
        recent_notifications = Notification.objects.filter(recipient=user).order_by(
            "-created_at"
        )[:5]
        context["recent_notifications"] = recent_notifications

        # Непрочитанные уведомления
        unread_count = Notification.objects.filter(
            recipient=user, is_read=False
        ).count()
        context["unread_notifications_count"] = unread_count

        # Критичные непрочитанные уведомления
        critical_unread = Notification.objects.filter(
            recipient=user,
            priority="critical",
            requires_acknowledgment=True,
            acknowledged_at__isnull=True,
        ).count()
        context["critical_unread_count"] = critical_unread

        # Последние пропуски детей
        recent_absences = AbsenceHistory.objects.filter(
            child__in=children, lesson_date__gte=date.today() - timedelta(days=30)
        ).order_by("-lesson_date")[:10]
        context["recent_absences"] = recent_absences

        # Предстоящие пробные занятия
        upcoming_trials = TrialLesson.objects.filter(
            child__in=children, status="scheduled", scheduled_date__gte=date.today()
        ).order_by("scheduled_date")
        context["upcoming_trials"] = upcoming_trials

        return context


class ChildDashboardView(DashboardView):
    """Dashboard для детей"""

    template_name = "clients/child_dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.userprofile.is_child:
            messages.error(request, "Zugriff verweigert.")
            return redirect("/login/")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Получаем профиль ребенка
        try:
            child = Child.objects.get(user=user)
            context["child"] = child
        except Child.DoesNotExist:
            messages.error(self.request, "Kinderprofil nicht gefunden.")
            return context

        # Активные зачисления в группы
        active_enrollments = (
            GroupEnrollment.objects.filter(child=child, status="active")
            .select_related("group__subject")
            .prefetch_related("group__teachers")
        )
        context["active_enrollments"] = active_enrollments

        # Расписание на текущую неделю
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        weekly_schedule = []
        for enrollment in active_enrollments:
            schedules = enrollment.group.schedules.filter(
                is_active=True, valid_from__lte=today
            ).filter(Q(valid_to__isnull=True) | Q(valid_to__gte=today))

            for schedule in schedules:
                weekly_schedule.append(
                    {
                        "group": enrollment.group,
                        "schedule": schedule,
                        "weekday": schedule.get_weekday_display(),
                        "time": schedule.start_time,
                        "duration": schedule.duration,
                        "classroom": schedule.classroom,
                    }
                )

        context["weekly_schedule"] = sorted(
            weekly_schedule, key=lambda x: (x["schedule"].weekday, x["time"])
        )

        # Последние занятия
        recent_lessons = ActualLesson.objects.filter(
            group__in=[e.group for e in active_enrollments],
            scheduled_date__gte=date.today() - timedelta(days=30),
        ).order_by("-scheduled_date")[:10]
        context["recent_lessons"] = recent_lessons

        # История посещаемости
        attendance_records = []
        for lesson in recent_lessons:
            attendance = lesson.attendance_records.filter(child=child).first()
            if attendance:
                attendance_records.append({"lesson": lesson, "attendance": attendance})
        context["attendance_records"] = attendance_records[:10]

        # История пропусков
        absence_history = AbsenceHistory.objects.filter(
            child=child, lesson_date__gte=date.today() - timedelta(days=60)
        ).order_by("-lesson_date")[:10]
        context["absence_history"] = absence_history

        # Уведомления
        recent_notifications = Notification.objects.filter(recipient=user).order_by(
            "-created_at"
        )[:5]
        context["recent_notifications"] = recent_notifications

        # Статистика посещаемости
        total_lessons = len(attendance_records)
        present_lessons = len(
            [a for a in attendance_records if a["attendance"].status == "present"]
        )
        if total_lessons > 0:
            attendance_percentage = (present_lessons / total_lessons) * 100
            context["attendance_percentage"] = round(attendance_percentage, 1)
        else:
            context["attendance_percentage"] = 0

        return context


class TeacherDashboardView(DashboardView):
    """Dashboard для учителей"""

    template_name = "clients/teacher_dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.userprofile.is_teacher:
            messages.error(request, "Zugriff verweigert.")
            return redirect("/login/")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Группы учителя
        teacher_groups = (
            Group.objects.filter(teachers=user, is_active=True)
            .select_related("subject")
            .prefetch_related("groupenrollment_set")
        )
        context["teacher_groups"] = teacher_groups

        # Сегодняшние занятия
        today = date.today()
        today_lessons = ActualLesson.objects.filter(
            Q(scheduled_teacher=user) | Q(actual_teacher=user),
            scheduled_date__date=today,
        ).order_by("scheduled_date")
        context["today_lessons"] = today_lessons

        # Занятия на этой неделе
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        week_lessons = ActualLesson.objects.filter(
            Q(scheduled_teacher=user) | Q(actual_teacher=user),
            scheduled_date__date__range=[week_start, week_end],
        ).order_by("scheduled_date")
        context["week_lessons"] = week_lessons

        # Ожидающие отметки занятия
        pending_lessons = ActualLesson.objects.filter(
            scheduled_teacher=user,
            status="scheduled",
            scheduled_date__lt=today + timedelta(days=1),
        ).order_by("-scheduled_date")
        context["pending_lessons"] = pending_lessons

        # Статистика учителя
        total_lessons_this_month = ActualLesson.objects.filter(
            Q(scheduled_teacher=user) | Q(actual_teacher=user),
            scheduled_date__month=today.month,
            scheduled_date__year=today.year,
        ).count()

        conducted_lessons_this_month = ActualLesson.objects.filter(
            actual_teacher=user,
            status="conducted",
            scheduled_date__month=today.month,
            scheduled_date__year=today.year,
        ).count()

        substitutions_this_month = (
            ActualLesson.objects.filter(
                actual_teacher=user,
                status="conducted",
                scheduled_date__month=today.month,
                scheduled_date__year=today.year,
            )
            .exclude(scheduled_teacher=user)
            .count()
        )

        context.update(
            {
                "total_lessons_this_month": total_lessons_this_month,
                "conducted_lessons_this_month": conducted_lessons_this_month,
                "substitutions_this_month": substitutions_this_month,
            }
        )

        # Студенты учителя
        all_students = set()
        for group in teacher_groups:
            for enrollment in group.groupenrollment_set.filter(status="active"):
                all_students.add(enrollment.child)
        context["total_students"] = len(all_students)

        # Последние уведомления
        recent_notifications = Notification.objects.filter(recipient=user).order_by(
            "-created_at"
        )[:5]
        context["recent_notifications"] = recent_notifications

        return context


@login_required
def notifications_view(request):
    """Страница уведомлений"""
    notifications = Notification.objects.filter(recipient=request.user).order_by(
        "-created_at"
    )

    # Фильтрация
    filter_type = request.GET.get("type")
    if filter_type:
        notifications = notifications.filter(notification_type=filter_type)

    # Показывать только непрочитанные
    if request.GET.get("unread") == "true":
        notifications = notifications.filter(is_read=False)

    context = {
        "notifications": notifications,
        "notification_types": Notification.NOTIFICATION_TYPES,
        "current_filter": filter_type,
    }

    return render(request, "clients/notifications.html", context)


@login_required
def mark_notification_read(request, notification_id):
    """Отмечает уведомление как прочитанное"""
    notification = get_object_or_404(
        Notification, id=notification_id, recipient=request.user
    )

    notification.mark_as_read()

    if request.headers.get("HX-Request"):  # HTMX запрос
        return render(
            request, "clients/notification_item.html", {"notification": notification}
        )

    return redirect("notifications")


@login_required
def acknowledge_notification(request, notification_id):
    """Подтверждает получение критичного уведомления"""
    notification = get_object_or_404(
        Notification,
        id=notification_id,
        recipient=request.user,
        requires_acknowledgment=True,
    )

    notification.acknowledge()
    messages.success(request, "Benachrichtigung wurde bestatigt.")

    return redirect("notifications")


@login_required
def profile_view(request):
    """Просмотр профиля пользователя"""
    return render(request, "clients/profile.html")


@login_required
def edit_profile_view(request):
    """Редактирование профиля"""
    user = request.user

    if request.method == "POST":
        user_form = UserForm(request.POST, instance=user)
        profile_form = UserProfileForm(
            request.POST, instance=user.userprofile, user=user
        )

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, "Profil wurde erfolgreich aktualisiert.")
            return redirect("clients:profile")
    else:
        user_form = UserForm(instance=user)
        profile_form = UserProfileForm(instance=user.userprofile, user=user)

    context = {
        "user_form": user_form,
        "profile_form": profile_form,
    }
    return render(request, "clients/edit_profile.html", context)


@login_required
def children_list_view(request):
    """Список детей (для родителей)"""
    if not request.user.userprofile.is_parent:
        messages.error(request, "Zugriff verweigert.")
        return redirect("clients:home")

    children = (
        Child.objects.filter(parent=request.user, is_active=True)
        .select_related("user")
        .prefetch_related("groupenrollment_set__group__subject")
    )
    context = {"children": children}
    return render(request, "clients/children_list.html", context)


@login_required
def child_detail_view(request, child_id):
    """Детали ребенка"""
    child = get_object_or_404(Child, id=child_id)

    # Проверяем права доступа
    if not (
        request.user == child.parent
        or request.user == child.user
        or request.user.userprofile.role in ["admin", "teacher"]
    ):
        messages.error(request, "Zugriff verweigert.")
        return redirect("clients:home")

    context = {"child": child}
    return render(request, "clients/child_detail.html", context)


@login_required
def child_schedule_view(request, child_id):
    """Расписание ребенка"""
    child = get_object_or_404(Child, id=child_id)

    # Проверяем права доступа
    if not (
        request.user == child.parent
        or request.user == child.user
        or request.user.userprofile.role in ["admin", "teacher"]
    ):
        messages.error(request, "Zugriff verweigert.")
        return redirect("clients:home")

    # Получаем активные зачисления
    enrollments = (
        GroupEnrollment.objects.filter(child=child, status="active")
        .select_related("group__subject")
        .prefetch_related("group__schedules")
    )

    context = {
        "child": child,
        "enrollments": enrollments,
    }
    return render(request, "clients/child_schedule.html", context)


@login_required
def child_attendance_view(request, child_id):
    """История посещаемости ребенка"""
    child = get_object_or_404(Child, id=child_id)

    # Проверяем права доступа
    if not (
        request.user == child.parent
        or request.user == child.user
        or request.user.userprofile.role in ["admin", "teacher"]
    ):
        messages.error(request, "Zugriff verweigert.")
        return redirect("clients:home")

    # Получаем все записи об отсутствиях для данного ребенка (для статистики)
    all_absences = AbsenceHistory.objects.filter(child=child).order_by("-lesson_date")

    # Вычисляем статистику по типам отсутствий
    total_count = all_absences.count()
    excused_count = all_absences.filter(absence_type="excused").count()
    unexcused_count = all_absences.filter(absence_type="unexcused").count()

    # Получаем только последние 50 записей для отображения
    absence_history = all_absences[:50]

    context = {
        "child": child,
        "absence_history": absence_history,
        "total_count": total_count,
        "excused_count": excused_count,
        "unexcused_count": unexcused_count,
    }
    return render(request, "clients/child_attendance.html", context)


@login_required
def clients_list_view(request):
    """Список клиентов (для админов)"""
    if not request.user.userprofile.role in ["admin", "accountant"]:
        return redirect("home")

    # Получаем всех пользователей с профилями
    profiles = UserProfile.objects.select_related("user").all()

    context = {
        "profiles": profiles,
    }
    return render(request, "clients/clients_list.html", context)


@login_required
def dashboard_redirect_view(request):
    """Перенаправляет пользователя в соответствующий dashboard"""
    user = request.user
    if hasattr(user, "userprofile"):
        role = user.userprofile.role
        if role == "parent":
            return redirect("clients:parent_dashboard")
        elif role == "child":
            return redirect("clients:child_dashboard")
        elif role == "teacher":
            return redirect("clients:teacher_dashboard")
        elif role in ["admin", "accountant"]:
            return render(request, "dashboard.html", {"title": "Dashboard"})
    return redirect("clients:home")
