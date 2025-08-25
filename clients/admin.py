from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import Child, UserProfile


class UserProfileInline(admin.StackedInline):
    """Инлайн для профиля пользователя"""

    model = UserProfile
    can_delete = False
    verbose_name_plural = "Benutzerprofil"
    extra = 0
    fields = (
        "role",
        "phone",
        "address",
        "birth_date",
        "iban",
        "bic",
        "bank_name",
        "specialization",
        "hire_date",
    )

    def get_fieldsets(self, request, obj=None):
        """Динамические fieldsets в зависимости от роли"""
        if obj and hasattr(obj, "userprofile"):
            role = obj.userprofile.role
            if role == "parent":
                return (
                    (
                        "Основная информация",
                        {"fields": ("role", "phone", "address", "birth_date")},
                    ),
                    (
                        "Банковские данные",
                        {
                            "fields": ("iban", "bic", "bank_name"),
                            "classes": ("collapse",),
                        },
                    ),
                )
            elif role == "teacher":
                return (
                    (
                        "Основная информация",
                        {"fields": ("role", "phone", "address", "birth_date")},
                    ),
                    (
                        "Профессиональная информация",
                        {"fields": ("specialization", "hire_date")},
                    ),
                )

        return super().get_fieldsets(request, obj)


class UserAdmin(BaseUserAdmin):
    """Расширенная админка для пользователей"""

    inlines = (UserProfileInline,)
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "get_role",
        "get_phone",
        "is_active",
        "date_joined",
    )
    list_filter = ("is_active", "is_staff", "userprofile__role", "date_joined")
    search_fields = (
        "username",
        "first_name",
        "last_name",
        "email",
        "userprofile__phone",
    )

    def get_role(self, obj):
        """Получает роль пользователя"""
        if hasattr(obj, "userprofile"):
            return obj.userprofile.get_role_display()
        return "-"

    get_role.short_description = "Rolle"
    get_role.admin_order_field = "userprofile__role"

    def get_phone(self, obj):
        """Получает телефон пользователя"""
        if hasattr(obj, "userprofile"):
            return obj.userprofile.phone or "-"
        return "-"

    get_phone.short_description = "Telefon"

    def get_queryset(self, request):
        """Оптимизируем запросы для списка детей"""
        return (
            super()
            .get_queryset(request)
            .select_related("parent__user")
            .prefetch_related("groupenrollment_set__group__subject")
        )


# Перерегистрируем админку пользователей
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Админка для профилей пользователей"""

    list_display = ("user", "role", "phone", "get_email", "created_at")
    list_filter = ("role", "created_at", "updated_at")
    search_fields = ("user__first_name", "user__last_name", "user__email", "phone")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (
            "Основная информация",
            {"fields": ("user", "role", "phone", "address", "birth_date")},
        ),
        (
            "Банковские данные",
            {"fields": ("iban", "bic", "bank_name"), "classes": ("collapse",)},
        ),
        (
            "Для учителей",
            {"fields": ("specialization", "hire_date"), "classes": ("collapse",)},
        ),
        (
            "Системная информация",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def get_email(self, obj):
        """Получает email пользователя"""
        return obj.user.email

    get_email.short_description = "E-Mail"
    get_email.admin_order_field = "user__email"

    def get_queryset(self, request):
        """Оптимизация запросов"""
        qs = super().get_queryset(request)
        return qs.select_related("user")


@admin.register(Child)
class ChildAdmin(admin.ModelAdmin):
    """Админка для детей"""

    list_display = (
        "get_full_name",
        "parent",
        "age",
        "school_class",
        "get_active_subjects",
        "is_active",
    )
    list_filter = ("is_active", "school_class", "created_at")
    search_fields = (
        "user__first_name",
        "user__last_name",
        "parent__first_name",
        "parent__last_name",
    )
    readonly_fields = ("created_at", "updated_at", "age")

    fieldsets = (
        (
            "Основная информация",
            {"fields": ("user", "parent", "birth_date", "school_class", "is_active")},
        ),
        (
            "Дополнительная информация",
            {
                "fields": ("medical_notes", "special_needs", "notes"),
                "classes": ("collapse",),
            },
        ),
        (
            "Системная информация",
            {"fields": ("created_at", "updated_at", "age"), "classes": ("collapse",)},
        ),
    )

    def get_full_name(self, obj):
        """Получает полное имя ребенка"""
        return obj.user.get_full_name()

    get_full_name.short_description = "Name"
    get_full_name.admin_order_field = "user__first_name"

    def get_active_subjects(self, obj):
        """Получает активные предметы ребенка"""
        subjects = obj.current_subjects
        if subjects:
            subject_links = []
            for subject in subjects[:3]:  # Показываем только первые 3
                url = reverse("admin:lessons_subject_change", args=[subject.id])
                subject_links.append(f'<a href="{url}">{subject.name}</a>')

            result = ", ".join(subject_links)
            if len(subjects) > 3:
                result += f" (+{len(subjects) - 3} weitere)"
            return mark_safe(result)
        return "-"

    get_active_subjects.short_description = "Aktive Faecher"

    def get_queryset(self, request):
        """Оптимизация запросов"""
        qs = super().get_queryset(request)
        return qs.select_related("user", "parent").prefetch_related(
            "groupenrollment_set__group__subject"
        )

    actions = ["activate_children", "deactivate_children"]

    def activate_children(self, request, queryset):
        """Активирует выбранных детей"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} Kinder wurden aktiviert.")

    activate_children.short_description = "Ausgewaehlte Kinder aktivieren"

    def deactivate_children(self, request, queryset):
        """Деактивирует выбранных детей"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} Kinder wurden deaktiviert.")

    deactivate_children.short_description = "Ausgewaehlte Kinder deaktivieren"


# Настройка заголовка админки
admin.site.site_header = "Bildungszentrum Verwaltung"
admin.site.site_title = "Bildungszentrum Admin"
admin.site.index_title = "Willkommen in der Bildungszentrum Verwaltung"
