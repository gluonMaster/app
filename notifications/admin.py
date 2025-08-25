from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Q
from .models import Notification, ChangeLog


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Админка для уведомлений"""
    list_display = ('title', 'recipient', 'notification_type', 'priority', 
                   'get_status_display', 'created_at')
    list_filter = ('notification_type', 'priority', 'is_read', 'is_important', 
                  'requires_acknowledgment', 'created_at')
    search_fields = ('title', 'message', 'recipient__first_name', 'recipient__last_name')
    readonly_fields = ('created_at', 'read_at', 'acknowledged_at', 'content_object')
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('recipient', 'notification_type', 'priority', 'title', 'message')
        }),
        ('Статус', {
            'fields': ('is_read', 'is_important', 'requires_acknowledgment')
        }),
        ('Временные метки', {
            'fields': ('created_at', 'read_at', 'acknowledged_at'),
            'classes': ('collapse',)
        }),
        ('Связанный объект', {
            'fields': ('content_object',),
            'classes': ('collapse',)
        }),
    )
    
    def get_status_display(self, obj):
        """Отображает статус уведомления с цветовым кодированием"""
        status_parts = []
        
        # Статус прочтения
        if obj.is_read:
            status_parts.append('<span style="color: green;">✓ Gelesen</span>')
        else:
            if obj.priority == 'critical':
                status_parts.append('<span style="color: red; font-weight: bold;">⚠ Ungelesen</span>')
            else:
                status_parts.append('<span style="color: orange;">○ Ungelesen</span>')
        
        # Важность
        if obj.is_important:
            status_parts.append('<span style="color: purple;">★ Wichtig</span>')
        
        # Требуется подтверждение
        if obj.requires_acknowledgment:
            if obj.acknowledged_at:
                status_parts.append('<span style="color: green;">✓ Bestaetigt</span>')
            else:
                status_parts.append('<span style="color: red;">⚠ Bestaetigung erforderlich</span>')
        
        return mark_safe(' | '.join(status_parts))
    get_status_display.short_description = 'Status'
    
    def get_queryset(self, request):
        """Оптимизация запросов"""
        qs = super().get_queryset(request)
        return qs.select_related('recipient', 'content_type')
    
    actions = ['mark_as_read', 'mark_as_important', 'send_reminder']
    
    def mark_as_read(self, request, queryset):
        """Отмечает уведомления как прочитанные"""
        from django.utils import timezone
        updated = 0
        for notification in queryset.filter(is_read=False):
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save()
            updated += 1
        self.message_user(request, f'{updated} Benachrichtigungen wurden als gelesen markiert.')
    mark_as_read.short_description = 'Als gelesen markieren'
    
    def mark_as_important(self, request, queryset):
        """Отмечает уведомления как важные"""
        updated = queryset.update(is_important=True)
        self.message_user(request, f'{updated} Benachrichtigungen wurden als wichtig markiert.')
    mark_as_important.short_description = 'Als wichtig markieren'
    
    def send_reminder(self, request, queryset):
        """Отправляет напоминания о непрочитанных критичных уведомлениях"""
        critical_unread = queryset.filter(
            priority='critical',
            is_read=False,
            requires_acknowledgment=True,
            acknowledged_at__isnull=True
        )
        
        reminded = 0
        for notification in critical_unread:
            # Создаем напоминание
            Notification.objects.create(
                recipient=notification.recipient,
                notification_type='general',
                priority='critical',
                title=f'ERINNERUNG: {notification.title}',
                message=f'Sie haben eine wichtige Benachrichtigung noch nicht bestaetigt:\n\n{notification.message}',
                requires_acknowledgment=True,
                content_object=notification.content_object
            )
            reminded += 1
        
        self.message_user(request, f'{reminded} Erinnerungen wurden gesendet.')
    send_reminder.short_description = 'Erinnerungen senden'


@admin.register(ChangeLog)
class ChangeLogAdmin(admin.ModelAdmin):
    """Админка для журнала изменений"""
    list_display = ('table_name', 'record_id', 'field_name', 'changed_by', 'changed_at')
    list_filter = ('table_name', 'changed_at', 'changed_by')
    search_fields = ('table_name', 'field_name', 'old_value', 'new_value', 'change_reason')
    readonly_fields = ('changed_at',)
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('table_name', 'record_id', 'field_name')
        }),
        ('Изменения', {
            'fields': ('old_value', 'new_value', 'change_reason')
        }),
        ('Системная информация', {
            'fields': ('changed_by', 'changed_at')
        }),
    )
    
    def has_add_permission(self, request):
        """Запрещает ручное добавление записей в лог"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Запрещает изменение записей в логе"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Разрешает удаление только суперпользователям"""
        return request.user.is_superuser


# Кастомная страница статистики уведомлений
from django.shortcuts import render
from django.urls import path
from django.contrib.admin.views.decorators import staff_member_required

@staff_member_required
def notification_stats(request):
    """Страница статистики уведомлений"""
    from django.db.models import Count, Q
    from datetime import datetime, timedelta
    
    # Общая статистика
    total_notifications = Notification.objects.count()
    unread_notifications = Notification.objects.filter(is_read=False).count()
    critical_unacknowledged = Notification.objects.filter(
        priority='critical',
        requires_acknowledgment=True,
        acknowledged_at__isnull=True
    ).count()
    
    # Статистика по типам
    type_stats = Notification.objects.values('notification_type').annotate(
        total=Count('id'),
        unread=Count('id', filter=Q(is_read=False))
    ).order_by('-total')
    
    # Статистика по пользователям с наибольшим количеством непрочитанных
    user_stats = Notification.objects.filter(is_read=False).values(
        'recipient__first_name', 'recipient__last_name'
    ).annotate(
        unread_count=Count('id')
    ).order_by('-unread_count')[:10]
    
    # Статистика за последние 7 дней
    week_ago = datetime.now() - timedelta(days=7)
    recent_stats = Notification.objects.filter(created_at__gte=week_ago).values(
        'created_at__date'
    ).annotate(
        count=Count('id')
    ).order_by('created_at__date')
    
    context = {
        'title': 'Benachrichtigungsstatistik',
        'total_notifications': total_notifications,
        'unread_notifications': unread_notifications,
        'critical_unacknowledged': critical_unacknowledged,
        'type_stats': type_stats,
        'user_stats': user_stats,
        'recent_stats': recent_stats,
    }
    
    return render(request, 'admin/notification_stats.html', context)


# Расширение админки
class NotificationAdminSite(admin.AdminSite):
    """Кастомная админка с дополнительными страницами"""
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('notification-stats/', notification_stats, name='notification_stats'),
        ]
        return custom_urls + urls


# Регистрация кастомных действий
def create_sample_notifications(modeladmin, request, queryset):
    """Создает тестовые уведомления для выбранных пользователей"""
    from django.contrib.auth.models import User
    
    created = 0
    for user in User.objects.filter(is_active=True)[:5]:  # Только первые 5 активных пользователей
        Notification.objects.create(
            recipient=user,
            notification_type='general',
            priority='normal',
            title='Testbenachrichtigung',
            message='Dies ist eine Testbenachrichtigung zur Überprüfung des Systems.'
        )
        created += 1
    
    modeladmin.message_user(request, f'{created} Testbenachrichtigungen wurden erstellt.')

create_sample_notifications.short_description = 'Testbenachrichtigungen erstellen'

# Добавляем действие к админке пользователей
from django.contrib.auth.admin import UserAdmin
UserAdmin.actions = list(UserAdmin.actions) + [create_sample_notifications]