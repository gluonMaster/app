from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class Subject(models.Model):
    """Модель предмета"""

    name = models.CharField(max_length=100, verbose_name="Fachname")
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    code = models.CharField(
        max_length=10, unique=True, verbose_name="Fachcode"
    )  # например, "MATH1", "DE2"
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")

    # Базовые настройки предмета
    default_duration = models.IntegerField(
        default=45, verbose_name="Standard Dauer (Minuten)"
    )  # академический час = 45 минут
    min_age = models.IntegerField(null=True, blank=True, verbose_name="Mindestalter")
    max_age = models.IntegerField(null=True, blank=True, verbose_name="Hoechstalter")

    # Дополнительная информация
    required_materials = models.TextField(
        blank=True, verbose_name="Erforderliche Materialien"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")

    class Meta:
        verbose_name = "Fach"
        verbose_name_plural = "Faecher"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def clean(self):
        """Валидация модели"""
        super().clean()

        # Проверяем логичность возрастных ограничений
        if self.min_age and self.max_age and self.min_age > self.max_age:
            raise ValidationError(
                {"max_age": "Hoechstalter kann nicht kleiner als Mindestalter sein"}
            )

    @property
    def current_price(self):
        """Возвращает текущую цену предмета"""
        from datetime import date

        from contracts.models import PriceList

        current_price = (
            PriceList.objects.filter(
                subject=self, valid_from__lte=date.today(), is_active=True
            )
            .order_by("-valid_from")
            .first()
        )

        return current_price.price_per_hour if current_price else None


class Group(models.Model):
    """Модель учебной группы"""

    GROUP_TYPES = [
        ("group", "Gruppenunterricht"),
        ("individual", "Einzelunterricht"),
        ("nachhilfe", "Nachhilfe"),
    ]

    name = models.CharField(max_length=100, verbose_name="Gruppenname")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, verbose_name="Fach")
    group_type = models.CharField(
        max_length=15, choices=GROUP_TYPES, default="group", verbose_name="Gruppentyp"
    )
    teachers = models.ManyToManyField(
        User, limit_choices_to={"userprofile__role": "teacher"}, verbose_name="Lehrer"
    )

    level = models.CharField(
        max_length=50, blank=True, verbose_name="Niveau"
    )  # "Anfaenger", "Fortgeschrittene"
    min_age = models.IntegerField(null=True, blank=True, verbose_name="Mindestalter")
    max_age = models.IntegerField(null=True, blank=True, verbose_name="Hoechstalter")
    max_students = models.IntegerField(
        default=12, verbose_name="Maximale Teilnehmerzahl"
    )  # Для индивидуальных = 1

    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    notes = models.TextField(blank=True, verbose_name="Notizen")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")

    class Meta:
        verbose_name = "Gruppe"
        verbose_name_plural = "Gruppen"
        ordering = ["subject__name", "name"]

    def __str__(self):
        return f"{self.name} - {self.subject.name}"

    def clean(self):
        """Валидация модели"""
        super().clean()

        # Для индивидуальных занятий максимум 1 студент
        if self.group_type == "individual" and self.max_students > 1:
            self.max_students = 1

    @property
    def current_enrollment_count(self):
        """Текущее количество зачисленных студентов"""
        return self.groupenrollment_set.filter(status="active").count()

    @property
    def available_spots(self):
        """Доступные места в группе"""
        return self.max_students - self.current_enrollment_count

    @property
    def is_full(self):
        """Проверяет, заполнена ли группа"""
        return self.available_spots <= 0


class Schedule(models.Model):
    """Модель расписания группы"""

    WEEKDAYS = [
        (0, "Montag"),
        (1, "Dienstag"),
        (2, "Mittwoch"),
        (3, "Donnerstag"),
        (4, "Freitag"),
        (5, "Samstag"),
        (6, "Sonntag"),
    ]

    group = models.ForeignKey(
        Group, on_delete=models.CASCADE, related_name="schedules", verbose_name="Gruppe"
    )
    weekday = models.IntegerField(choices=WEEKDAYS, verbose_name="Wochentag")
    start_time = models.TimeField(verbose_name="Startzeit")
    duration = models.IntegerField(
        verbose_name="Dauer (Minuten)"
    )  # продолжительность в минутах

    # Период действия расписания
    valid_from = models.DateField(verbose_name="Gueltig ab")
    valid_to = models.DateField(null=True, blank=True, verbose_name="Gueltig bis")

    # Дополнительная информация
    classroom = models.CharField(max_length=50, blank=True, verbose_name="Klassenraum")
    notes = models.TextField(blank=True, verbose_name="Notizen")
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")

    class Meta:
        verbose_name = "Stundenplan"
        verbose_name_plural = "Stundenplaene"
        ordering = ["weekday", "start_time"]

    def __str__(self):
        return f"{self.group.name} - {self.get_weekday_display()} {self.start_time}"

    @property
    def end_time(self):
        """Вычисляет время окончания занятия"""
        start_datetime = datetime.combine(datetime.today(), self.start_time)
        end_datetime = start_datetime + timedelta(minutes=self.duration)
        return end_datetime.time()


class GroupEnrollment(models.Model):
    """Модель зачисления детей в группы"""

    STATUS_CHOICES = [
        ("active", "Aktiv"),
        ("suspended", "Ausgesetzt"),
        ("completed", "Abgeschlossen"),
        ("transferred", "In andere Gruppe uebertragen"),
    ]

    child = models.ForeignKey(
        "clients.Child", on_delete=models.CASCADE, verbose_name="Kind"
    )
    group = models.ForeignKey(Group, on_delete=models.CASCADE, verbose_name="Gruppe")
    contract_item = models.ForeignKey(
        "contracts.ContractItem",
        on_delete=models.CASCADE,
        verbose_name="Vertragsposition",
    )

    status = models.CharField(
        max_length=15, choices=STATUS_CHOICES, default="active", verbose_name="Status"
    )
    enrollment_date = models.DateField(verbose_name="Anmeldedatum")
    end_date = models.DateField(null=True, blank=True, verbose_name="Enddatum")

    notes = models.TextField(blank=True, verbose_name="Notizen")

    class Meta:
        verbose_name = "Gruppenanmeldung"
        verbose_name_plural = "Gruppenanmeldungen"
        unique_together = ["child", "group", "contract_item"]

    def __str__(self):
        return f"{self.child.user.get_full_name()} in {self.group.name}"


class ActualLesson(models.Model):
    """Модель фактического проведения занятий"""

    LESSON_STATUS = [
        ("scheduled", "Geplant"),
        ("conducted", "Durchgefuehrt"),
        ("cancelled", "Abgesagt"),
        ("rescheduled", "Verschoben"),
    ]

    group = models.ForeignKey(Group, on_delete=models.CASCADE, verbose_name="Gruppe")
    scheduled_teacher = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="scheduled_lessons",
        verbose_name="Geplanter Lehrer",
    )
    actual_teacher = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="conducted_lessons",
        null=True,
        blank=True,
        verbose_name="Tatsaechlicher Lehrer",
    )

    scheduled_date = models.DateTimeField(verbose_name="Geplante Zeit")
    actual_date = models.DateTimeField(
        null=True, blank=True, verbose_name="Tatsaechliche Zeit"
    )
    duration = models.IntegerField(
        verbose_name="Dauer (Minuten)"
    )  # фактическая продолжительность в минутах
    status = models.CharField(
        max_length=15, choices=LESSON_STATUS, default="scheduled", verbose_name="Status"
    )

    # Примечания о занятии
    lesson_content = models.TextField(blank=True, verbose_name="Unterrichtsinhalt")
    homework_assigned = models.TextField(blank=True, verbose_name="Hausaufgaben")
    notes = models.TextField(blank=True, verbose_name="Notizen")

    # Административная информация
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")
    updated_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="updated_lessons",
        verbose_name="Aktualisiert von",
    )

    class Meta:
        verbose_name = "Tatsaechlicher Unterricht"
        verbose_name_plural = "Tatsaechlicher Unterricht"
        ordering = ["-scheduled_date"]

    def __str__(self):
        return f"{self.group.name} - {self.scheduled_date.strftime('%d.%m.%Y %H:%M')}"

    @property
    def is_substitution(self):
        """Проверяет, было ли замещение учителя"""
        return self.actual_teacher and self.actual_teacher != self.scheduled_teacher


class AttendanceRecord(models.Model):
    """Модель записи посещаемости"""

    ATTENDANCE_STATUS = [
        ("present", "Anwesend"),
        ("absent", "Abwesend"),
        ("late", "Verspaetet"),
        ("excused", "Entschuldigt"),
    ]

    lesson = models.ForeignKey(
        ActualLesson,
        on_delete=models.CASCADE,
        related_name="attendance_records",
        verbose_name="Unterricht",
    )
    child = models.ForeignKey(
        "clients.Child", on_delete=models.CASCADE, verbose_name="Kind"
    )
    status = models.CharField(
        max_length=15, choices=ATTENDANCE_STATUS, verbose_name="Anwesenheitsstatus"
    )
    arrival_time = models.TimeField(null=True, blank=True, verbose_name="Ankunftszeit")
    departure_time = models.TimeField(null=True, blank=True, verbose_name="Abgangszeit")
    notes = models.TextField(blank=True, verbose_name="Notizen")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    marked_by = models.ForeignKey(
        User, on_delete=models.PROTECT, verbose_name="Markiert von"
    )

    class Meta:
        verbose_name = "Anwesenheitsrekord"
        verbose_name_plural = "Anwesenheitsrekorde"
        unique_together = ["lesson", "child"]

    def __str__(self):
        return f"{self.child.user.get_full_name()} - {self.get_status_display()}"


class AbsenceHistory(models.Model):
    """Модель истории пропусков"""

    child = models.ForeignKey(
        "clients.Child",
        on_delete=models.CASCADE,
        related_name="absence_history",
        verbose_name="Kind",
    )
    lesson_date = models.DateTimeField(verbose_name="Unterrichtsdatum")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, verbose_name="Fach")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, verbose_name="Gruppe")
    absence_type = models.CharField(
        max_length=15,
        choices=AttendanceRecord.ATTENDANCE_STATUS,
        verbose_name="Art der Abwesenheit",
    )
    excuse_provided = models.BooleanField(
        default=False, verbose_name="Entschuldigung vorgelegt"
    )
    excuse_reason = models.TextField(blank=True, verbose_name="Entschuldigungsgrund")

    # Автоматическое уведомление родителей
    parent_notified = models.BooleanField(
        default=False, verbose_name="Eltern benachrichtigt"
    )
    notification_sent_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Benachrichtigung gesendet am"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")

    class Meta:
        verbose_name = "Fehlzeitenhistorie"
        verbose_name_plural = "Fehlzeitenhistorien"
        ordering = ["-lesson_date"]

    def __str__(self):
        return f"{self.child.user.get_full_name()} - {self.subject.name} ({self.lesson_date.strftime('%d.%m.%Y')})"


class TrialLesson(models.Model):
    """Модель пробных занятий"""

    TRIAL_STATUS = [
        ("scheduled", "Geplant"),
        ("completed", "Durchgefuehrt"),
        ("cancelled", "Abgesagt"),
        ("no_show", "Nicht erschienen"),
    ]

    child = models.ForeignKey(
        "clients.Child", on_delete=models.CASCADE, verbose_name="Kind"
    )
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, verbose_name="Fach")
    teacher = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="taught_trials",
        verbose_name="Lehrer",
    )

    scheduled_date = models.DateTimeField(verbose_name="Geplante Zeit")
    actual_date = models.DateTimeField(
        null=True, blank=True, verbose_name="Tatsaechliche Zeit"
    )
    duration = models.IntegerField(default=45, verbose_name="Dauer (Minuten)")
    status = models.CharField(
        max_length=15, choices=TRIAL_STATUS, default="scheduled", verbose_name="Status"
    )

    # Результат пробного занятия
    teacher_feedback = models.TextField(blank=True, verbose_name="Lehrerrueckmeldung")
    recommended_level = models.CharField(
        max_length=50, blank=True, verbose_name="Empfohlenes Niveau"
    )
    recommended_group = models.ForeignKey(
        Group,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Empfohlene Gruppe",
    )
    enrolled_after_trial = models.BooleanField(
        default=False, verbose_name="Nach Probestunde angemeldet"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="created_trials",
        verbose_name="Erstellt von",
    )
    notes = models.TextField(blank=True, verbose_name="Notizen")

    class Meta:
        verbose_name = "Probestunde"
        verbose_name_plural = "Probestunden"
        ordering = ["-scheduled_date"]

    def __str__(self):
        return f"Probestunde: {self.child.user.get_full_name()} - {self.subject.name}"
