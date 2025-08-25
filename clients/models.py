from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class UserProfile(models.Model):
    """Расширение стандартной модели User Django"""
    
    ROLE_CHOICES = [
        ('parent', 'Elternteil'),          # Родитель
        ('child', 'Kind'),                 # Ребенок
        ('teacher', 'Lehrer'),            # Учитель
        ('admin', 'Administrator'),        # Администратор
        ('accountant', 'Buchhalter'),     # Бухгалтер
    ]
    
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE,
        verbose_name="Benutzer"
    )
    role = models.CharField(
        max_length=15, 
        choices=ROLE_CHOICES,
        verbose_name="Rolle"
    )
    phone = models.CharField(
        max_length=20, 
        blank=True, 
        verbose_name="Telefon"
    )
    address = models.TextField(
        blank=True, 
        verbose_name="Adresse"
    )
    birth_date = models.DateField(
        null=True, 
        blank=True, 
        verbose_name="Geburtsdatum"
    )
    
    # Для родителей - банковские реквизиты
    iban = models.CharField(
        max_length=34, 
        blank=True, 
        verbose_name="IBAN"
    )
    bic = models.CharField(
        max_length=11, 
        blank=True, 
        verbose_name="BIC"
    )
    bank_name = models.CharField(
        max_length=100, 
        blank=True, 
        verbose_name="Bankname"
    )
    
    # Дополнительные поля для учителей
    specialization = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Spezialisierung"
    )
    hire_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Einstellungsdatum"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Erstellt am"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Aktualisiert am"
    )
    
    class Meta:
        verbose_name = "Benutzerprofil"
        verbose_name_plural = "Benutzerprofile"
        
    def __str__(self):
        return f"{self.user.get_full_name()} ({self.get_role_display()})"
    
    def clean(self):
        """Валидация модели"""
        super().clean()
        
        # Для родителей обязательны банковские данные при SEPA
        if self.role == 'parent' and hasattr(self, 'contracts'):
            sepa_contracts = self.contracts.filter(payment_type='sepa').exists()
            if sepa_contracts and not self.iban:
                raise ValidationError({
                    'iban': 'IBAN ist erforderlich fuer SEPA-Zahlungen'
                })
    
    @property
    def is_parent(self):
        return self.role == 'parent'
    
    @property
    def is_teacher(self):
        return self.role == 'teacher'
    
    @property
    def is_child(self):
        return self.role == 'child'
    
    @property
    def is_admin(self):
        return self.role == 'admin'
    
    @property
    def is_accountant(self):
        return self.role == 'accountant'


class Child(models.Model):
    """Модель ребенка"""
    
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE,
        verbose_name="Benutzer"
    )
    parent = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='children',
        verbose_name="Elternteil"
    )
    birth_date = models.DateField(
        verbose_name="Geburtsdatum"
    )
    school_class = models.CharField(
        max_length=10, 
        blank=True,
        verbose_name="Schulklasse"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Notizen"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktiv"
    )
    
    # Медицинская информация и особенности
    medical_notes = models.TextField(
        blank=True,
        verbose_name="Medizinische Hinweise"
    )
    special_needs = models.TextField(
        blank=True,
        verbose_name="Besondere Beduerfnisse"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Erstellt am"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Aktualisiert am"
    )
    
    class Meta:
        verbose_name = "Kind"
        verbose_name_plural = "Kinder"
        ordering = ['user__first_name', 'user__last_name']
    
    def __str__(self):
        return f"{self.user.get_full_name()} ({self.age} Jahre)"
    
    def clean(self):
        """Валидация модели"""
        super().clean()
        
        # Проверяем, что родитель действительно имеет роль 'parent'
        if not hasattr(self.parent, 'userprofile') or self.parent.userprofile.role != 'parent':
            raise ValidationError({
                'parent': 'Der ausgewaehlte Benutzer ist kein Elternteil'
            })
    
    @property
    def age(self):
        """Вычисляет возраст ребенка"""
        from datetime import date
        today = date.today()
        return today.year - self.birth_date.year - (
            (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
        )
    
    @property
    def active_enrollments(self):
        """Возвращает активные зачисления в группы"""
        return self.groupenrollment_set.filter(status='active')
    
    @property
    def current_subjects(self):
        """Возвращает текущие изучаемые предметы"""
        return [enrollment.group.subject for enrollment in self.active_enrollments]