from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from clients.models import Child

from .forms import ActualLessonForm, LessonAttendanceForm, TrialLessonBookingForm
from .models import (
    AbsenceHistory,
    ActualLesson,
    AttendanceRecord,
    Group,
    GroupEnrollment,
    Schedule,
    Subject,
    TrialLesson,
)


@login_required
def teacher_lesson_detail(request, lesson_id):
    """Детальная страница занятия для учителя"""
    if not request.user.userprofile.is_teacher:
        messages.error(request, "Zugriff verweigert.")
        return redirect("login")

    lesson = get_object_or_404(
        ActualLesson, id=lesson_id, scheduled_teacher=request.user
    )

    # Получаем всех студентов группы
    enrolled_students = lesson.group.groupenrollment_set.filter(
        status="active"
    ).select_related("child__user")

    # Получаем записи посещаемости
    attendance_records = lesson.attendance_records.all()
    attendance_dict = {record.child_id: record for record in attendance_records}

    context = {
        "lesson": lesson,
        "enrolled_students": enrolled_students,
        "attendance_dict": attendance_dict,
    }

    return render(request, "lessons/teacher_lesson_detail.html", context)


@login_required
@require_POST
def mark_lesson_attendance(request, lesson_id):
    """Отмечает посещаемость занятия"""
    if not request.user.userprofile.is_teacher:
        return JsonResponse({"error": "Zugriff verweigert"}, status=403)

    lesson = get_object_or_404(
        ActualLesson, id=lesson_id, scheduled_teacher=request.user
    )

    # Обновляем статус занятия
    lesson.status = "conducted"
    lesson.actual_teacher = request.user
    lesson.actual_date = lesson.scheduled_date
    lesson.updated_by = request.user

    # Обновляем содержание занятия
    lesson.lesson_content = request.POST.get("lesson_content", "")
    lesson.homework_assigned = request.POST.get("homework_assigned", "")
    lesson.notes = request.POST.get("notes", "")
    lesson.save()

    # Обрабатываем посещаемость
    enrolled_students = lesson.group.groupenrollment_set.filter(status="active")

    for enrollment in enrolled_students:
        child = enrollment.child
        attendance_status = request.POST.get(f"attendance_{child.id}", "absent")
        arrival_time = request.POST.get(f"arrival_time_{child.id}")
        departure_time = request.POST.get(f"departure_time_{child.id}")
        notes = request.POST.get(f"notes_{child.id}", "")

        # Создаем или обновляем запись посещаемости
        attendance, created = AttendanceRecord.objects.get_or_create(
            lesson=lesson,
            child=child,
            defaults={"status": attendance_status, "marked_by": request.user},
        )

        if not created:
            attendance.status = attendance_status
            attendance.notes = notes
            attendance.save()

        # Если студент отсутствовал, создаем запись в истории пропусков
        if attendance_status in ["absent", "excused"]:
            AbsenceHistory.objects.get_or_create(
                child=child,
                lesson_date=lesson.scheduled_date,
                subject=lesson.group.subject,
                group=lesson.group,
                defaults={
                    "absence_type": attendance_status,
                    "excuse_provided": attendance_status == "excused",
                },
            )

    messages.success(request, "Anwesenheit wurde erfolgreich markiert.")
    return redirect("clients:teacher_dashboard")


@login_required
def update_lesson_content(request, lesson_id):
    """Обновляет содержание проведенного занятия"""
    if not request.user.userprofile.is_teacher:
        messages.error(request, "Zugriff verweigert.")
        return redirect("login")

    lesson = get_object_or_404(ActualLesson, id=lesson_id, actual_teacher=request.user)

    if request.method == "POST":
        form = ActualLessonForm(request.POST, instance=lesson)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.updated_by = request.user
            lesson.save()
            messages.success(request, "Unterrichtsinhalt wurde aktualisiert.")
            return redirect("clients:teacher_dashboard")
    else:
        form = ActualLessonForm(instance=lesson)

    context = {
        "form": form,
        "lesson": lesson,
    }

    return render(request, "lessons/update_lesson_content.html", context)


@login_required
def subjects_list_view(request):
    """Список предметов"""
    subjects = Subject.objects.filter(is_active=True).order_by("name")

    context = {"subjects": subjects, "title": "Verfügbare Fächer"}

    return render(request, "lessons/subjects_list.html", context)


@login_required
def groups_list_view(request):
    """Список групп"""
    groups = (
        Group.objects.filter(is_active=True)
        .select_related("subject")
        .prefetch_related("teachers")
    )

    # Фильтрация
    subject_filter = request.GET.get("subject")
    if subject_filter:
        groups = groups.filter(subject_id=subject_filter)

    # Только группы с доступными местами
    if request.GET.get("available_only") == "true":
        groups = [g for g in groups if not g.is_full]

    context = {
        "groups": groups,
        "subjects": Subject.objects.filter(is_active=True),
        "subject_filter": subject_filter,
        "title": "Gruppen",
    }

    return render(request, "lessons/groups_list.html", context)


@login_required
def group_detail_view(request, group_id):
    """Детальная страница группы"""
    group = get_object_or_404(Group, id=group_id)

    # Получаем расписание группы
    schedules = group.schedules.filter(is_active=True).order_by("weekday", "start_time")

    # Получаем зачисленных студентов
    enrollments = group.groupenrollment_set.filter(status="active").select_related(
        "child__user"
    )

    # Проверяем, может ли пользователь видеть эту информацию
    can_view_details = False
    if request.user.userprofile.role in ["admin", "accountant", "teacher"]:
        can_view_details = True
    elif request.user.userprofile.is_parent:
        # Родитель может видеть, если его ребенок в группе
        child_in_group = enrollments.filter(child__parent=request.user).exists()
        can_view_details = child_in_group
    elif request.user.userprofile.is_child:
        # Ребенок может видеть, если он в группе
        child_in_group = enrollments.filter(child__user=request.user).exists()
        can_view_details = child_in_group

    context = {
        "group": group,
        "schedules": schedules,
        "enrollments": enrollments if can_view_details else [],
        "can_view_details": can_view_details,
        "title": f"Gruppe: {group.name}",
    }

    return render(request, "lessons/group_detail.html", context)


@login_required
def group_schedule_view(request, group_id):
    """Расписание конкретной группы"""
    group = get_object_or_404(Group, id=group_id)

    schedules = group.schedules.filter(is_active=True).order_by("weekday", "start_time")

    context = {
        "group": group,
        "schedules": schedules,
        "title": f"Stundenplan: {group.name}",
    }

    return render(request, "lessons/group_schedule.html", context)


@login_required
def teacher_lessons_view(request):
    """Список занятий для учителя"""
    if not request.user.userprofile.is_teacher:
        messages.error(request, "Zugriff verweigert.")
        return redirect("login")

    from datetime import date, timedelta

    # Фильтры
    status_filter = request.GET.get("status", "all")
    date_filter = request.GET.get("date", "week")

    lessons = ActualLesson.objects.filter(
        Q(scheduled_teacher=request.user) | Q(actual_teacher=request.user)
    ).select_related("group__subject")

    # Фильтр по статусу
    if status_filter != "all":
        lessons = lessons.filter(status=status_filter)

    # Фильтр по дате
    today = date.today()
    if date_filter == "today":
        lessons = lessons.filter(scheduled_date__date=today)
    elif date_filter == "week":
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        lessons = lessons.filter(scheduled_date__date__range=[week_start, week_end])
    elif date_filter == "month":
        lessons = lessons.filter(
            scheduled_date__year=today.year, scheduled_date__month=today.month
        )

    lessons = lessons.order_by("-scheduled_date")

    context = {
        "lessons": lessons,
        "status_filter": status_filter,
        "date_filter": date_filter,
        "lesson_statuses": ActualLesson.LESSON_STATUS,
        "title": "Meine Unterrichtsstunden",
    }

    return render(request, "lessons/teacher_lessons.html", context)


@login_required
def teacher_groups_view(request):
    """Группы учителя"""
    if not request.user.userprofile.is_teacher:
        messages.error(request, "Zugriff verweigert.")
        return redirect("login")

    groups = (
        Group.objects.filter(teachers=request.user, is_active=True)
        .select_related("subject")
        .prefetch_related("groupenrollment_set__child__user")
    )

    context = {"groups": groups, "title": "Meine Gruppen"}

    return render(request, "lessons/teacher_groups.html", context)


@login_required
def teacher_students_view(request):
    """Студенты учителя"""
    if not request.user.userprofile.is_teacher:
        messages.error(request, "Zugriff verweigert.")
        return redirect("login")

    # Получаем всех студентов из групп учителя
    enrollments = (
        GroupEnrollment.objects.filter(group__teachers=request.user, status="active")
        .select_related("child__user", "group__subject")
        .order_by("child__user__first_name")
    )

    context = {"enrollments": enrollments, "title": "Meine Schüler"}

    return render(request, "lessons/teacher_students.html", context)


@login_required
def schedule_view(request):
    """Общее расписание"""
    schedules = (
        Schedule.objects.filter(is_active=True)
        .select_related("group__subject")
        .prefetch_related("group__teachers")
        .order_by("weekday", "start_time")
    )

    # Группируем по дням недели
    weekly_schedule = {}
    for schedule in schedules:
        day_name = schedule.get_weekday_display()
        if day_name not in weekly_schedule:
            weekly_schedule[day_name] = []
        weekly_schedule[day_name].append(schedule)

    context = {"weekly_schedule": weekly_schedule, "title": "Stundenplan"}

    return render(request, "lessons/schedule.html", context)


@login_required
def weekly_schedule_view(request):
    """Недельное расписание в табличном виде"""
    from datetime import date, timedelta

    # Получаем текущую неделю
    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    schedules = (
        Schedule.objects.filter(is_active=True)
        .select_related("group__subject")
        .prefetch_related("group__teachers")
        .order_by("weekday", "start_time")
    )

    # Если пользователь - ребенок, показываем только его расписание
    if request.user.userprofile.is_child:
        try:
            child = Child.objects.get(user=request.user)
            child_groups = [e.group for e in child.active_enrollments]
            schedules = schedules.filter(group__in=child_groups)
        except Child.DoesNotExist:
            schedules = Schedule.objects.none()

    # Если пользователь - учитель, показываем его группы
    elif request.user.userprofile.is_teacher:
        schedules = schedules.filter(group__teachers=request.user)

    context = {"schedules": schedules, "week_start": week_start, "title": "Wochenplan"}

    return render(request, "lessons/weekly_schedule.html", context)


@login_required
def trial_lessons_view(request):
    """Список пробных занятий"""
    if request.user.userprofile.is_parent:
        children = Child.objects.filter(parent=request.user, is_active=True)
        trials = TrialLesson.objects.filter(child__in=children).order_by(
            "-scheduled_date"
        )
    elif request.user.userprofile.is_child:
        try:
            child = Child.objects.get(user=request.user)
            trials = TrialLesson.objects.filter(child=child).order_by("-scheduled_date")
        except Child.DoesNotExist:
            trials = TrialLesson.objects.none()
    else:
        trials = TrialLesson.objects.all().order_by("-scheduled_date")

    # Статистики для отображения
    total_trials = trials.count()
    scheduled_count = trials.filter(status="scheduled").count()
    conducted_count = trials.filter(
        status="completed"
    ).count()  # исправлено с "conducted" на "completed"
    cancelled_count = trials.filter(status="cancelled").count()
    no_show_count = trials.filter(status="no_show").count()
    interested_count = trials.filter(
        enrolled_after_trial=True
    ).count()  # используем enrolled_after_trial

    context = {
        "trials": trials,
        "title": "Probestunden",
        "total_trials": total_trials,
        "scheduled_count": scheduled_count,
        "conducted_count": conducted_count,
        "cancelled_count": cancelled_count,
        "no_show_count": no_show_count,
        "interested_count": interested_count,
    }

    return render(request, "lessons/trial_lessons.html", context)


@login_required
def book_trial_lesson(request):
    """Запись на пробное занятие"""
    if not request.user.userprofile.is_parent:
        messages.error(request, "Zugriff verweigert.")
        return redirect("login")

    if request.method == "POST":
        form = TrialLessonBookingForm(request.POST, parent=request.user)
        if form.is_valid():
            trial = form.save(commit=False)
            trial.created_by = request.user
            trial.save()

            messages.success(request, "Probestunde wurde erfolgreich gebucht.")
            return redirect("lessons:trial_lessons")
    else:
        form = TrialLessonBookingForm(parent=request.user)

    context = {"form": form, "title": "Probestunde buchen"}

    return render(request, "lessons/book_trial.html", context)


@login_required
def trial_lesson_detail(request, trial_id):
    """Детали пробного занятия"""
    trial = get_object_or_404(TrialLesson, id=trial_id)

    # Проверяем права доступа
    can_view = False
    if request.user.userprofile.role in ["admin", "accountant", "teacher"]:
        can_view = True
    elif request.user.userprofile.is_parent and trial.child.parent == request.user:
        can_view = True
    elif request.user.userprofile.is_child and trial.child.user == request.user:
        can_view = True

    if not can_view:
        messages.error(request, "Zugriff verweigert.")
        return redirect("login")

    context = {"trial": trial, "title": f"Probestunde: {trial.subject.name}"}

    return render(request, "lessons/trial_detail.html", context)


@login_required
def attendance_view(request):
    """Посещаемость"""
    if request.user.userprofile.is_child:
        try:
            child = Child.objects.get(user=request.user)
            base_absences = AbsenceHistory.objects.filter(child=child).order_by(
                "-lesson_date"
            )
        except Child.DoesNotExist:
            base_absences = AbsenceHistory.objects.none()
    elif request.user.userprofile.is_parent:
        children = Child.objects.filter(parent=request.user, is_active=True)
        base_absences = AbsenceHistory.objects.filter(child__in=children).order_by(
            "-lesson_date"
        )
    else:
        base_absences = AbsenceHistory.objects.all().order_by("-lesson_date")

    # Статистики для отображения (без среза)
    total_absences = base_absences.count()
    absent_count = base_absences.filter(absence_type="absent").count()
    excused_count = base_absences.filter(absence_type="excused").count()
    late_count = base_absences.filter(absence_type="late").count()
    sick_count = base_absences.filter(absence_type="sick").count()

    # Применяем срез только для отображения списка
    if request.user.userprofile.is_child:
        absences = base_absences[:20]
    elif request.user.userprofile.is_parent:
        absences = base_absences[:50]
    else:
        absences = base_absences[:100]

    context = {
        "absences": absences,
        "title": "Anwesenheit",
        "total_absences": total_absences,
        "absent_count": absent_count,
        "excused_count": excused_count,
        "late_count": late_count,
        "sick_count": sick_count,
    }

    return render(request, "lessons/attendance.html", context)


@login_required
def absences_view(request):
    """История пропусков (alias для attendance_view)"""
    return attendance_view(request)


@login_required
def lessons_index_view(request):
    """Главная страница уроков"""
    context = {
        "title": "Уроки",
    }
    return render(request, "lessons/lessons_index.html", context)
