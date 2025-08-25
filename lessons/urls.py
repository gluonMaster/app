from django.urls import path

from . import views

app_name = "lessons"

urlpatterns = [
    # Главная страница уроков
    path("", views.lessons_index_view, name="lessons_index"),
    # Предметы и группы
    path("subjects/", views.subjects_list_view, name="subjects_list"),
    path("groups/", views.groups_list_view, name="groups_list"),
    path("groups/<int:group_id>/", views.group_detail_view, name="group_detail"),
    path(
        "groups/<int:group_id>/schedule/",
        views.group_schedule_view,
        name="group_schedule",
    ),
    # Для учителей
    path("teacher/lessons/", views.teacher_lessons_view, name="teacher_lessons"),
    path(
        "teacher/lessons/<int:lesson_id>/",
        views.teacher_lesson_detail,
        name="teacher_lesson_detail",
    ),
    path(
        "teacher/lessons/<int:lesson_id>/attendance/",
        views.mark_lesson_attendance,
        name="mark_lesson_attendance",
    ),
    path(
        "teacher/lessons/<int:lesson_id>/content/",
        views.update_lesson_content,
        name="update_lesson_content",
    ),
    path("teacher/groups/", views.teacher_groups_view, name="teacher_groups"),
    path("teacher/students/", views.teacher_students_view, name="teacher_students"),
    # Расписание
    path("schedule/", views.schedule_view, name="schedule"),
    path("schedule/week/", views.weekly_schedule_view, name="weekly_schedule"),
    # Пробные занятия
    path("trials/", views.trial_lessons_view, name="trial_lessons"),
    path("trials/book/", views.book_trial_lesson, name="book_trial_lesson"),
    path(
        "trials/<int:trial_id>/", views.trial_lesson_detail, name="trial_lesson_detail"
    ),
    # Посещаемость и пропуски
    path("attendance/", views.attendance_view, name="attendance"),
    path("absences/", views.absences_view, name="absences"),
]
