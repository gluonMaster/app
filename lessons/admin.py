from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Q
from .models import (
    Subject, Group, Schedule, GroupEnrollment, ActualLesson, 
    AttendanceRecord, AbsenceHistory, TrialLesson
)


class ScheduleInline(admin.TabularInline):
    """Инлайн для расписания группы"""
    model = Schedule
    extra = 0
    fields = ('weekday', 'start_time', 'duration', 'classroom', 'valid_from', 'valid_to', 'is_active')


class GroupEnrollmentInline(admin.TabularInline):
    """Инлайн для зачислений в группу"""
    model = GroupEnrollment
    extra = 0
    fields = ('child', 'status', 'enrollment_date', 'end_date')
    readonly_fields = ('enrollment_date',)


class AttendanceRecordInline(admin.TabularInline):
    """Инлайн для записей посещаемости"""
    model = AttendanceRecord
    extra = 0
    fields = ('child', 'status', 'arrival_time', 'departure_time', 'notes')
    readonly_fields = ('marked_by',)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    """Админка для предметов"""
    list_display = ('name', 'code', 'default_duration', 'get_age_range', 
                   'get_current_price', 'get_active_groups', 'is_active')
    list_filter = ('is_active', 'default_duration', 'created_at')
    search_fields = ('name', 'code', 'description')
    readonly_fields = ('created_at', 'updated_at', 'current_price')
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'code', 'description', 'is_active')
        }),
        ('Настройки', {
            'fields': ('default_duration', 'min_age', 'max_age', 'required_materials')
        }),
        ('Системная информация', {
            'fields': ('current_price', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_age_range(self, obj):
        """Получает возрастной диапазон"""
        if obj.min_age and obj.max_age:
            return f"{obj.min_age}-{obj.max_age} Jahre"
        elif obj.min_age:
            return f"ab {obj.min_age} Jahre"
        elif obj.max_age:
            return f"bis {obj.max_age} Jahre"
        return "Alle Altersgruppen"
    get_age_range.short_description = 'Altersgruppe'
    
    def get_current_price(self, obj):
        """Получает текущую цену"""
        price = obj.current_price
        if price:
            return f"{price}€/Std."
        return "Nicht festgelegt"
    get_current_price.short_description = 'Aktueller Preis'
    
    def get_active_groups(self, obj):
        """Получает количество активных групп"""
        count = obj.group_set.filter(is_active=True).count()
        if count > 0:
            url = reverse('admin:lessons_group_changelist') + f'?subject__id__exact={obj.id}'
            return format_html('<a href="{}">{} Gruppen</a>', url, count)
        return "0 Gruppen"
    get_active_groups.short_description = 'Aktive Gruppen'


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    """Админка для групп"""
    list_display = ('name', 'subject', 'group_type', 'get_teachers_list', 
                   'get_enrollment_info', 'level', 'is_active')
    list_filter = ('group_type', 'is_active', 'subject', 'level')
    search_fields = ('name', 'subject__name', 'level')
    filter_horizontal = ('teachers',)
    readonly_fields = ('created_at', 'updated_at', 'current_enrollment_count', 'available_spots')
    inlines = [ScheduleInline, GroupEnrollmentInline]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'subject', 'group_type', 'level', 'is_active')
        }),
        ('Учителя', {
            'fields': ('teachers',)
        }),
        ('Настройки группы', {
            'fields': ('min_age', 'max_age', 'max_students')
        }),
        ('Статистика', {
            'fields': ('current_enrollment_count', 'available_spots'),
            'classes': ('collapse',)
        }),
        ('Дополнительно', {
            'fields': ('notes', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_teachers_list(self, obj):
        """Получает список учителей"""
        teachers = obj.teachers.all()[:3]  # Показываем только первых 3
        if teachers:
            teacher_links = []
            for teacher in teachers:
                url = reverse('admin:auth_user_change', args=[teacher.id])
                teacher_links.append(f'<a href="{url}">{teacher.get_full_name()}</a>')
            
            result = ', '.join(teacher_links)
            if obj.teachers.count() > 3:
                result += f' (+{obj.teachers.count() - 3} weitere)'
            return mark_safe(result)
        return "Keine Lehrer"
    get_teachers_list.short_description = 'Lehrer'
    
    def get_enrollment_info(self, obj):
        """Получает информацию о зачислениях"""
        current = obj.current_enrollment_count
        max_students = obj.max_students
        
        # Цветовое кодирование заполненности
        if current >= max_students:
            return format_html('<span style="color: red; font-weight: bold;">{}/{}</span>', current, max_students)
        elif current >= max_students * 0.8:
            return format_html('<span style="color: orange;">{}/{}</span>', current, max_students)
        else:
            return format_html('<span style="color: green;">{}/{}</span>', current, max_students)
    get_enrollment_info.short_description = 'Belegung'


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    """Админка для расписания"""
    list_display = ('group', 'get_weekday_time', 'duration', 'classroom', 
                   'valid_from', 'valid_to', 'is_active')
    list_filter = ('weekday', 'is_active', 'valid_from', 'group__subject')
    search_fields = ('group__name', 'classroom')
    readonly_fields = ('end_time',)
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('group', 'weekday', 'start_time', 'duration', 'classroom')
        }),
        ('Период действия', {
            'fields': ('valid_from', 'valid_to', 'is_active')
        }),
        ('Дополнительно', {
            'fields': ('end_time', 'notes'),
            'classes': ('collapse',)
        }),
    )
    
    def get_weekday_time(self, obj):
        """Получает день недели и время"""
        return f"{obj.get_weekday_display()}, {obj.start_time} ({obj.duration} Min.)"
    get_weekday_time.short_description = 'Zeit'


@admin.register(GroupEnrollment)
class GroupEnrollmentAdmin(admin.ModelAdmin):
    """Админка для зачислений в группы"""
    list_display = ('child', 'group', 'status', 'enrollment_date', 'end_date')
    list_filter = ('status', 'enrollment_date', 'group__subject')
    search_fields = ('child__user__first_name', 'child__user__last_name', 'group__name')
    readonly_fields = ('enrollment_date',)
    
    actions = ['activate_enrollments', 'suspend_enrollments', 'complete_enrollments']
    
    def activate_enrollments(self, request, queryset):
        """Активирует зачисления"""
        updated = queryset.update(status='active')
        self.message_user(request, f'{updated} Anmeldungen wurden aktiviert.')
    activate_enrollments.short_description = 'Anmeldungen aktivieren'
    
    def suspend_enrollments(self, request, queryset):
        """Приостанавливает зачисления"""
        updated = queryset.update(status='suspended')
        self.message_user(request, f'{updated} Anmeldungen wurden ausgesetzt.')
    suspend_enrollments.short_description = 'Anmeldungen aussetzen'
    
    def complete_enrollments(self, request, queryset):
        """Завершает зачисления"""
        from datetime import date
        updated = queryset.update(status='completed', end_date=date.today())
        self.message_user(request, f'{updated} Anmeldungen wurden abgeschlossen.')
    complete_enrollments.short_description = 'Anmeldungen abschliessen'


@admin.register(ActualLesson)
class ActualLessonAdmin(admin.ModelAdmin):
    """Админка для фактических занятий"""
    list_display = ('group', 'scheduled_date', 'actual_teacher', 'status', 
                   'duration', 'get_attendance_count', 'is_substitution')
    list_filter = ('status', 'scheduled_date', 'group__subject')
    search_fields = ('group__name', 'scheduled_teacher__first_name', 'actual_teacher__first_name')
    readonly_fields = ('created_at', 'updated_at', 'is_substitution')
    inlines = [AttendanceRecordInline]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('group', 'scheduled_teacher', 'actual_teacher', 'status')
        }),
        ('Время и продолжительность', {
            'fields': ('scheduled_date', 'actual_date', 'duration')
        }),
        ('Содержание занятия', {
            'fields': ('lesson_content', 'homework_assigned', 'notes'),
            'classes': ('collapse',)
        }),
        ('Системная информация', {
            'fields': ('is_substitution', 'created_at', 'updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    def get_attendance_count(self, obj):
        """Получает количество присутствующих"""
        present = obj.attendance_records.filter(status='present').count()
        total = obj.attendance_records.count()
        if total > 0:
            percentage = (present / total) * 100
            if percentage >= 90:
                color = 'green'
            elif percentage >= 70:
                color = 'orange'
            else:
                color = 'red'
            return format_html('<span style="color: {};">{}/{} ({}%)</span>', 
                             color, present, total, int(percentage))
        return "Keine Daten"
    get_attendance_count.short_description = 'Anwesenheit'
    
    def save_model(self, request, obj, form, change):
        """Автоматически устанавливает обновившего пользователя"""
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    
    actions = ['mark_as_conducted', 'mark_as_cancelled']
    
    def mark_as_conducted(self, request, queryset):
        """Отмечает как проведенные"""
        updated = queryset.update(status='conducted')
        self.message_user(request, f'{updated} Unterrichtsstunden wurden als durchgefuehrt markiert.')
    mark_as_conducted.short_description = 'Als durchgefuehrt markieren'
    
    def mark_as_cancelled(self, request, queryset):
        """Отмечает как отмененные"""
        updated = queryset.update(status='cancelled')
        self.message_user(request, f'{updated} Unterrichtsstunden wurden als abgesagt markiert.')
    mark_as_cancelled.short_description = 'Als abgesagt markieren'


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    """Админка для записей посещаемости"""
    list_display = ('lesson', 'child', 'status', 'arrival_time', 'departure_time', 'marked_by')
    list_filter = ('status', 'lesson__scheduled_date', 'lesson__group__subject')
    search_fields = ('child__user__first_name', 'child__user__last_name', 'lesson__group__name')
    readonly_fields = ('created_at', 'marked_by')
    
    def save_model(self, request, obj, form, change):
        """Автоматически устанавливает отметившего пользователя"""
        if not change:
            obj.marked_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(AbsenceHistory)
class AbsenceHistoryAdmin(admin.ModelAdmin):
    """Админка для истории пропусков"""
    list_display = ('child', 'subject', 'lesson_date', 'absence_type', 
                   'excuse_provided', 'parent_notified')
    list_filter = ('absence_type', 'excuse_provided', 'parent_notified', 'lesson_date')
    search_fields = ('child__user__first_name', 'child__user__last_name', 'subject__name')
    readonly_fields = ('created_at', 'notification_sent_at')
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('child', 'subject', 'group', 'lesson_date', 'absence_type')
        }),
        ('Оправдание', {
            'fields': ('excuse_provided', 'excuse_reason')
        }),
        ('Уведомления', {
            'fields': ('parent_notified', 'notification_sent_at'),
            'classes': ('collapse',)
        }),
        ('Системная информация', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_excused', 'notify_parents']
    
    def mark_excused(self, request, queryset):
        """Отмечает как оправданные"""
        updated = queryset.update(excuse_provided=True)
        self.message_user(request, f'{updated} Fehlzeiten wurden als entschuldigt markiert.')
    mark_excused.short_description = 'Als entschuldigt markieren'
    
    def notify_parents(self, request, queryset):
        """Уведомляет родителей"""
        from notifications.models import notify_absence
        from datetime import datetime
        
        updated = 0
        for absence in queryset.filter(parent_notified=False):
            notify_absence(absence)
            absence.parent_notified = True
            absence.notification_sent_at = datetime.now()
            absence.save()
            updated += 1
        
        self.message_user(request, f'{updated} Eltern wurden benachrichtigt.')
    notify_parents.short_description = 'Eltern benachrichtigen'


@admin.register(TrialLesson)
class TrialLessonAdmin(admin.ModelAdmin):
    """Админка для пробных занятий"""
    list_display = ('child', 'subject', 'teacher', 'scheduled_date', 'status', 'enrolled_after_trial')
    list_filter = ('status', 'enrolled_after_trial', 'scheduled_date', 'subject')
    search_fields = ('child__user__first_name', 'child__user__last_name', 'subject__name')
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('child', 'subject', 'teacher', 'status')
        }),
        ('Время', {
            'fields': ('scheduled_date', 'actual_date', 'duration')
        }),
        ('Результаты', {
            'fields': ('teacher_feedback', 'recommended_level', 'recommended_group', 'enrolled_after_trial')
        }),
        ('Дополнительно', {
            'fields': ('notes', 'created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Автоматически устанавливает создателя"""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    actions = ['mark_as_completed', 'mark_enrolled']
    
    def mark_as_completed(self, request, queryset):
        """Отмечает как проведенные"""
        updated = queryset.update(status='completed')
        self.message_user(request, f'{updated} Probestunden wurden als durchgefuehrt markiert.')
    mark_as_completed.short_description = 'Als durchgefuehrt markieren'
    
    def mark_enrolled(self, request, queryset):
        """Отмечает как зачисленные после пробного"""
        updated = queryset.update(enrolled_after_trial=True)
        self.message_user(request, f'{updated} Schueler wurden nach Probestunde angemeldet.')
    mark_enrolled.short_description = 'Als angemeldet markieren'