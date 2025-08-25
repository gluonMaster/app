from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
from datetime import date

class PriceList(models.Model):
    """Модель таблицы цен с историей"""
    
    subject = models.ForeignKey(
        'lessons.Subject', 
        on_delete=models.CASCADE,
        verbose_name="Fach"
    )
    price_per_hour = models.DecimalField(
        max_digits=8, 
        decimal_places=2,
        verbose_name="Preis pro Stunde"
    )
    valid_from = models.DateField(
        verbose_name="Gueltig ab"
    )
    valid_to = models.DateField(
        null=True, 
        blank=True,
        verbose_name="Gueltig bis"
    )
    created_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT,
        verbose_name="Erstellt von"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Erstellt am"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktiv"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Notizen"
    )  # причина изменения цены
    
    class Meta:
        verbose_name = "Preisliste"
        verbose_name_plural = "Preislisten"
        ordering = ['-valid_from']
    
    def __str__(self):
        return f"{self.subject.name}: {self.price_per_hour}€/Std. (ab {self.valid_from})"


class DiscountType(models.Model):
    """Модель типа скидки"""
    
    name = models.CharField(
        max_length=100,
        verbose_name="Name"
    )  # "Familienrabatt", "Mengenrabatt"
    description = models.TextField(
        blank=True,
        verbose_name="Beschreibung"
    )
    is_percentage = models.BooleanField(
        default=True,
        verbose_name="Prozentual"
    )  # процентная или абсолютная
    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktiv"
    )
    
    class Meta:
        verbose_name = "Rabatttyp"
        verbose_name_plural = "Rabatttypen"
    
    def __str__(self):
        return self.name


class Discount(models.Model):
    """Модель скидки"""
    
    discount_type = models.ForeignKey(
        DiscountType, 
        on_delete=models.CASCADE,
        verbose_name="Rabatttyp"
    )
    condition_description = models.CharField(
        max_length=200,
        verbose_name="Bedingung"
    )  # "Bei 3+ Faechern"
    value = models.DecimalField(
        max_digits=8, 
        decimal_places=2,
        verbose_name="Rabattwert"
    )  # размер скидки
    valid_from = models.DateField(
        verbose_name="Gueltig ab"
    )
    valid_to = models.DateField(
        null=True, 
        blank=True,
        verbose_name="Gueltig bis"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktiv"
    )
    
    # Условия применения скидки
    min_subjects = models.IntegerField(
        null=True, 
        blank=True,
        verbose_name="Mindestanzahl Faecher"
    )
    max_subjects = models.IntegerField(
        null=True, 
        blank=True,
        verbose_name="Hoechstanzahl Faecher"
    )
    applies_to_family = models.BooleanField(
        default=False,
        verbose_name="Familienrabatt"
    )  # семейная скидка
    
    class Meta:
        verbose_name = "Rabatt"
        verbose_name_plural = "Rabatte"
        ordering = ['-valid_from']
    
    def __str__(self):
        symbol = "%" if self.discount_type.is_percentage else "€"
        return f"{self.discount_type.name}: {self.value}{symbol}"


class Contract(models.Model):
    """Модель контракта"""
    
    CONTRACT_TYPES = [
        ('monthly', 'Monatlich'),
        ('yearly', 'Jaehrlich'),
        ('nachhilfe', 'Nachhilfe'),
        ('trial', 'Probestunden'),
        ('custom', 'Individuell'),
    ]
    
    PAYMENT_TYPES = [
        ('self', 'Selbstzahler'),
        ('sepa', 'SEPA'),
        ('jobcenter', 'JobCenter'),
        ('mixed', 'Gemischt'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Entwurf'),
        ('active', 'Aktiv'),
        ('completed', 'Abgeschlossen'),
        ('cancelled', 'Gekuendigt'),
        ('suspended', 'Ausgesetzt'),
    ]
    
    contract_number = models.CharField(
        max_length=20, 
        unique=True,
        verbose_name="Vertragsnummer"
    )
    parent = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='contracts',
        verbose_name="Elternteil"
    )
    contract_type = models.CharField(
        max_length=10, 
        choices=CONTRACT_TYPES,
        verbose_name="Vertragstyp"
    )
    payment_type = models.CharField(
        max_length=15, 
        choices=PAYMENT_TYPES,
        verbose_name="Zahlungsart"
    )
    status = models.CharField(
        max_length=15, 
        choices=STATUS_CHOICES, 
        default='draft',
        verbose_name="Status"
    )
    
    # Даты
    start_date = models.DateField(
        verbose_name="Startdatum"
    )
    end_date = models.DateField(
        verbose_name="Enddatum"
    )
    cancellation_deadline = models.DateField(
        verbose_name="Kuendigungsfrist"
    )  # до какой даты можно расторгнуть
    
    # Файлы
    contract_file = models.FileField(
        upload_to='contracts/', 
        null=True, 
        blank=True,
        verbose_name="Vertragsdatei"
    )
    
    # Аудит
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Erstellt am"
    )
    created_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='created_contracts',
        verbose_name="Erstellt von"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Aktualisiert am"
    )
    updated_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='updated_contracts', 
        null=True,
        verbose_name="Aktualisiert von"
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name="Notizen"
    )
    
    class Meta:
        verbose_name = "Vertrag"
        verbose_name_plural = "Vertraege"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Vertrag {self.contract_number} - {self.parent.get_full_name()}"
    
    def clean(self):
        """Валидация модели"""
        super().clean()
        
        # Проверяем логичность дат
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError({
                'end_date': 'Enddatum kann nicht vor Startdatum liegen'
            })
    
    @property
    def total_monthly_amount(self):
        """Общая ежемесячная сумма по контракту"""
        return sum(item.final_price for item in self.items.filter(is_active=True))
    
    @property
    def is_sepa_client(self):
        """Проверяет, является ли клиент SEPA-плательщиком"""
        return self.payment_type == 'sepa'


class ContractItem(models.Model):
    """Модель позиции контракта"""
    
    PAYER_CHOICES = [
        ('client', 'Kunde'),
        ('jobcenter', 'JobCenter'),
    ]
    
    contract = models.ForeignKey(
        Contract, 
        on_delete=models.CASCADE, 
        related_name='items',
        verbose_name="Vertrag"
    )
    child = models.ForeignKey(
        'clients.Child', 
        on_delete=models.CASCADE,
        verbose_name="Kind"
    )
    subject = models.ForeignKey(
        'lessons.Subject', 
        on_delete=models.CASCADE,
        verbose_name="Fach"
    )
    
    # Финансовые данные
    base_price = models.DecimalField(
        max_digits=8, 
        decimal_places=2,
        verbose_name="Grundpreis"
    )  # базовая цена
    price_date = models.DateField(
        verbose_name="Preisdatum"
    )  # дата установления базовой цены
    final_price = models.DecimalField(
        max_digits=8, 
        decimal_places=2,
        verbose_name="Endpreis"
    )  # итоговая цена после скидок
    payer = models.CharField(
        max_length=15, 
        choices=PAYER_CHOICES, 
        default='client',
        verbose_name="Zahler"
    )
    
    # Применяемые скидки
    applied_discounts = models.ManyToManyField(
        Discount, 
        through='ContractItemDiscount', 
        blank=True,
        verbose_name="Angewandte Rabatte"
    )
    
    # Дополнительная информация
    hours_per_month = models.IntegerField(
        default=4,
        verbose_name="Stunden pro Monat"
    )  # часов в месяц
    notes = models.TextField(
        blank=True,
        verbose_name="Notizen"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktiv"
    )
    
    class Meta:
        verbose_name = "Vertragsposition"
        verbose_name_plural = "Vertragspositionen"
        unique_together = ['contract', 'child', 'subject']
    
    def __str__(self):
        return f"{self.child.user.get_full_name()} - {self.subject.name}"
    
    def calculate_discounts(self):
        """Расчет применимых скидок"""
        total_discount = Decimal('0.00')
        
        # Получаем количество предметов в контракте
        subjects_count = self.contract.items.filter(is_active=True).count()
        
        # Применяем скидки
        applicable_discounts = Discount.objects.filter(
            is_active=True,
            valid_from__lte=date.today()
        ).filter(
            models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=date.today())
        )
        
        for discount in applicable_discounts:
            # Проверяем условия применения скидки
            if discount.min_subjects and subjects_count < discount.min_subjects:
                continue
            if discount.max_subjects and subjects_count > discount.max_subjects:
                continue
            
            # Рассчитываем размер скидки
            if discount.discount_type.is_percentage:
                discount_amount = self.base_price * discount.value / 100
            else:
                discount_amount = discount.value
            
            total_discount += discount_amount
        
        return total_discount
    
    def update_final_price(self):
        """Обновляет итоговую цену с учетом скидок"""
        discount_amount = self.calculate_discounts()
        self.final_price = max(self.base_price - discount_amount, Decimal('0.00'))
        self.save()


class ContractItemDiscount(models.Model):
    """Модель применяемых скидок к позициям контракта"""
    
    contract_item = models.ForeignKey(
        ContractItem, 
        on_delete=models.CASCADE,
        verbose_name="Vertragsposition"
    )
    discount = models.ForeignKey(
        Discount, 
        on_delete=models.CASCADE,
        verbose_name="Rabatt"
    )
    discount_amount = models.DecimalField(
        max_digits=8, 
        decimal_places=2,
        verbose_name="Rabattbetrag"
    )
    applied_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Angewandt am"
    )
    applied_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT,
        verbose_name="Angewandt von"
    )
    
    class Meta:
        verbose_name = "Angewandter Rabatt"
        verbose_name_plural = "Angewandte Rabatte"
    
    def __str__(self):
        return f"{self.discount.discount_type.name}: {self.discount_amount}€"


class ContractChangeRequest(models.Model):
    """Модель заявки на изменение контракта"""
    
    REQUEST_TYPES = [
        ('add_subject', 'Fach hinzufuegen'),
        ('remove_subject', 'Fach entfernen'),
        ('terminate_contract', 'Vertrag kuendigen'),
        ('new_contract', 'Neuer Vertrag'),
        ('change_schedule', 'Stundenplan aendern'),
        ('suspend_enrollment', 'Anmeldung aussetzen'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Ausstehend'),
        ('approved', 'Genehmigt'),
        ('rejected', 'Abgelehnt'),
        ('processing', 'In Bearbeitung'),
    ]
    
    # Основная информация
    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name='change_requests',
        null=True,
        blank=True,
        verbose_name="Vertrag"
    )
    parent = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='change_requests',
        verbose_name="Antragsteller"
    )
    child = models.ForeignKey(
        'clients.Child',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Kind"
    )
    
    # Тип и статус заявки
    request_type = models.CharField(
        max_length=20,
        choices=REQUEST_TYPES,
        verbose_name="Antragstyp"
    )
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Status"
    )
    
    # Детали заявки
    subject = models.ForeignKey(
        'lessons.Subject',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Fach"
    )
    requested_start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Gewuenschtes Startdatum"
    )
    requested_end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Gewuenschtes Enddatum"
    )
    
    # Финансовые данные (предварительный расчет)
    estimated_monthly_change = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Geschaetzte monatliche Aenderung"
    )
    
    # Описание и причины
    description = models.TextField(
        verbose_name="Beschreibung"
    )
    parent_reason = models.TextField(
        blank=True,
        verbose_name="Begruendung"
    )
    
    # Обработка администратором
    processed_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='processed_requests',
        verbose_name="Bearbeitet von"
    )
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Bearbeitet am"
    )
    admin_notes = models.TextField(
        blank=True,
        verbose_name="Admin-Notizen"
    )
    rejection_reason = models.TextField(
        blank=True,
        verbose_name="Ablehnungsgrund"
    )
    
    # Временные метки
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Erstellt am"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Aktualisiert am"
    )
    
    class Meta:
        verbose_name = "Vertragsaenderungsantrag"
        verbose_name_plural = "Vertragsaenderungsantraege"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_request_type_display()} - {self.parent.get_full_name()}"
    
    def calculate_estimated_change(self):
        """Рассчитывает предполагаемое изменение ежемесячной оплаты"""
        if self.request_type == 'add_subject' and self.subject:
            # Получаем текущую цену предмета
            current_price = self.subject.current_price
            if current_price:
                # Применяем скидки (упрощенный расчет)
                if self.contract:
                    current_subjects = self.contract.items.filter(is_active=True).count()
                    # Логика расчета скидок для нового количества предметов
                    # Здесь можно добавить более сложную логику
                self.estimated_monthly_change = current_price
        elif self.request_type == 'remove_subject':
            # Находим позицию контракта для удаления
            if self.contract and self.child and self.subject:
                try:
                    item = self.contract.items.get(
                        child=self.child,
                        subject=self.subject,
                        is_active=True
                    )
                    self.estimated_monthly_change = -item.final_price
                except ContractItem.DoesNotExist:
                    self.estimated_monthly_change = Decimal('0.00')


class OneTimeCharge(models.Model):
    """Модель разовых начислений"""
    
    CHARGE_TYPES = [
        ('library', 'Bibliotheksgebuehr'),
        ('costume', 'Kostueme/Requisiten'),
        ('materials', 'Unterrichtsmaterialien'),
        ('event', 'Veranstaltung'),
        ('registration', 'Anmeldegebuehr'),
        ('other', 'Sonstiges'),
    ]
    
    parent = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='one_time_charges',
        verbose_name="Elternteil"
    )
    child = models.ForeignKey(
        'clients.Child', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        verbose_name="Kind"
    )
    
    charge_type = models.CharField(
        max_length=15, 
        choices=CHARGE_TYPES,
        verbose_name="Gebuehrentyp"
    )
    description = models.CharField(
        max_length=200,
        verbose_name="Beschreibung"
    )
    amount = models.DecimalField(
        max_digits=8, 
        decimal_places=2,
        verbose_name="Betrag"
    )
    
    # Даты
    charge_date = models.DateField(
        verbose_name="Rechnungsdatum"
    )  # дата выставления
    due_date = models.DateField(
        verbose_name="Faelligkeitsdatum"
    )     # срок оплаты
    
    is_paid = models.BooleanField(
        default=False,
        verbose_name="Bezahlt"
    )
    paid_date = models.DateField(
        null=True, 
        blank=True,
        verbose_name="Zahlungsdatum"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Erstellt am"
    )
    created_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT,
        verbose_name="Erstellt von"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Notizen"
    )
    
    class Meta:
        verbose_name = "Einmalige Gebuehr"
        verbose_name_plural = "Einmalige Gebuehren"
        ordering = ['-charge_date']
    
    def __str__(self):
        return f"{self.get_charge_type_display()}: {self.amount}€"
    


class Invoice(models.Model):
    """Модель счета на оплату"""
    
    INVOICE_STATUS = [
        ('draft', 'Entwurf'),
        ('sent', 'Gesendet'),
        ('paid', 'Bezahlt'),
        ('overdue', 'Ueberfaellig'),
        ('cancelled', 'Storniert'),
    ]
    
    invoice_number = models.CharField(
        max_length=20, 
        unique=True,
        verbose_name="Rechnungsnummer"
    )
    parent = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='invoices',
        verbose_name="Kunde"
    )
    
    # Период счета
    period_start = models.DateField(
        verbose_name="Abrechnungszeitraum von"
    )
    period_end = models.DateField(
        verbose_name="Abrechnungszeitraum bis"
    )
    
    # Финансы
    subtotal = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Zwischensumme"
    )
    total_discount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        verbose_name="Gesamtrabatt"
    )
    total_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Gesamtbetrag"
    )
    
    # Статус и даты
    status = models.CharField(
        max_length=15, 
        choices=INVOICE_STATUS, 
        default='draft',
        verbose_name="Status"
    )
    issue_date = models.DateField(
        verbose_name="Rechnungsdatum"
    )
    due_date = models.DateField(
        verbose_name="Faelligkeitsdatum"
    )
    paid_date = models.DateField(
        null=True, 
        blank=True,
        verbose_name="Zahlungsdatum"
    )
    
    # Связанные объекты
    contract_items = models.ManyToManyField(
        'ContractItem', 
        blank=True,
        verbose_name="Vertragspositionen"
    )
    one_time_charges = models.ManyToManyField(
        'OneTimeCharge', 
        blank=True,
        verbose_name="Einmalige Gebuehren"
    )
    
    # Файлы
    invoice_file = models.FileField(
        upload_to='invoices/',
        null=True,
        blank=True,
        verbose_name="Rechnungsdatei"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Erstellt am"
    )
    created_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT,
        verbose_name="Erstellt von"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Notizen"
    )
    
    class Meta:
        verbose_name = "Rechnung"
        verbose_name_plural = "Rechnungen"
        ordering = ['-issue_date']
    
    def __str__(self):
        return f"Rechnung {self.invoice_number} - {self.parent.get_full_name()}"
    
    def clean(self):
        """Валидация модели"""
        super().clean()
        
        # Проверяем логичность дат
        if self.period_start and self.period_end and self.period_start > self.period_end:
            raise ValidationError({
                'period_end': 'Enddatum kann nicht vor Startdatum liegen'
            })
        
        if self.issue_date and self.due_date and self.issue_date > self.due_date:
            raise ValidationError({
                'due_date': 'Faelligkeitsdatum kann nicht vor Rechnungsdatum liegen'
            })
    
    @property
    def is_overdue(self):
        """Проверяет, просрочен ли счет"""
        from datetime import date
        return self.status != 'paid' and self.due_date < date.today()
    
    @property
    def days_overdue(self):
        """Количество дней просрочки"""
        if self.is_overdue:
            from datetime import date
            return (date.today() - self.due_date).days
        return 0
    
    def calculate_totals(self):
        """Пересчитывает общие суммы"""
        self.subtotal = sum(item.total_amount for item in self.items.all())
        self.total_discount = sum(item.discount_amount for item in self.items.all())
        self.total_amount = self.subtotal - self.total_discount
        self.save(update_fields=['subtotal', 'total_discount', 'total_amount'])


class InvoiceItem(models.Model):
    """Модель позиции счета (детализация)"""
    
    ITEM_TYPES = [
        ('regular', 'Regelmaessiger Unterricht'),
        ('individual', 'Einzelunterricht'),
        ('nachhilfe', 'Nachhilfe'),
        ('one_time', 'Einmalige Gebuehr'),
    ]
    
    invoice = models.ForeignKey(
        Invoice, 
        on_delete=models.CASCADE, 
        related_name='items',
        verbose_name="Rechnung"
    )
    item_type = models.CharField(
        max_length=15, 
        choices=ITEM_TYPES,
        verbose_name="Positionstyp"
    )
    
    description = models.CharField(
        max_length=300,
        verbose_name="Beschreibung"
    )
    child = models.ForeignKey(
        'clients.Child', 
        on_delete=models.CASCADE, 
        null=True,
        verbose_name="Kind"
    )
    subject = models.ForeignKey(
        'lessons.Subject', 
        on_delete=models.CASCADE, 
        null=True,
        verbose_name="Fach"
    )
    
    # Расчет
    quantity = models.DecimalField(
        max_digits=6, 
        decimal_places=2,
        verbose_name="Menge"
    )  # количество часов/занятий
    unit_price = models.DecimalField(
        max_digits=8, 
        decimal_places=2,
        verbose_name="Einzelpreis"
    )
    discount_amount = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        default=0,
        verbose_name="Rabattbetrag"
    )
    total_amount = models.DecimalField(
        max_digits=8, 
        decimal_places=2,
        verbose_name="Gesamtbetrag"
    )
    
    # Кто оплачивает
    payer = models.CharField(
        max_length=15, 
        choices=[('client', 'Kunde'), ('jobcenter', 'JobCenter')],
        verbose_name="Zahler"
    )
    
    class Meta:
        verbose_name = "Rechnungsposition"
        verbose_name_plural = "Rechnungspositionen"
    
    def __str__(self):
        return f"{self.description} - {self.total_amount}€"
    
    def save(self, *args, **kwargs):
        """Автоматический расчет общей суммы"""
        self.total_amount = (self.quantity * self.unit_price) - self.discount_amount
        super().save(*args, **kwargs)


class Payment(models.Model):
    """Модель платежа"""
    
    PAYMENT_METHODS = [
        ('cash', 'Bar'),
        ('bank_transfer', 'Ueberweisung'),
        ('sepa', 'SEPA-Lastschrift'),
        ('card', 'Kartenzahlung'),
        ('jobcenter', 'JobCenter'),
    ]
    
    PAYMENT_STATUS = [
        ('pending', 'Ausstehend'),
        ('completed', 'Abgeschlossen'),
        ('failed', 'Fehlgeschlagen'),
        ('refunded', 'Erstattet'),
    ]
    
    invoice = models.ForeignKey(
        Invoice, 
        on_delete=models.CASCADE, 
        related_name='payments',
        verbose_name="Rechnung"
    )
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Betrag"
    )
    payment_method = models.CharField(
        max_length=15, 
        choices=PAYMENT_METHODS,
        verbose_name="Zahlungsmethode"
    )
    status = models.CharField(
        max_length=15, 
        choices=PAYMENT_STATUS, 
        default='pending',
        verbose_name="Status"
    )
    
    payment_date = models.DateField(
        verbose_name="Zahlungsdatum"
    )
    reference_number = models.CharField(
        max_length=50, 
        blank=True,
        verbose_name="Referenznummer"
    )
    
    # Дополнительная информация
    bank_details = models.TextField(
        blank=True,
        verbose_name="Bankdaten"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Erstellt am"
    )
    created_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT,
        verbose_name="Erstellt von"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Notizen"
    )
    
    class Meta:
        verbose_name = "Zahlung"
        verbose_name_plural = "Zahlungen"
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"Zahlung {self.amount}€ - {self.invoice.invoice_number}"


class Debt(models.Model):
    """Модель задолженности (автоматически генерируемые)"""
    
    parent = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='debts',
        verbose_name="Schuldner"
    )
    invoice = models.OneToOneField(
        Invoice, 
        on_delete=models.CASCADE,
        verbose_name="Rechnung"
    )
    
    original_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Urspruenglicher Betrag"
    )
    remaining_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Restbetrag"
    )
    
    # Даты
    due_date = models.DateField(
        verbose_name="Faelligkeitsdatum"
    )
    overdue_since = models.DateField(
        null=True, 
        blank=True,
        verbose_name="Ueberfaellig seit"
    )  # с какой даты просрочено
    
    # Период формирования задолженности
    period_start = models.DateField(
        verbose_name="Zeitraum von"
    )
    period_end = models.DateField(
        verbose_name="Zeitraum bis"
    )
    
    is_resolved = models.BooleanField(
        default=False,
        verbose_name="Beglich"
    )
    resolved_date = models.DateField(
        null=True, 
        blank=True,
        verbose_name="Beglichen am"
    )
    
    # Штрафы и пени
    late_fee_applied = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        verbose_name="Mahngebuehren"
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
        verbose_name = "Schuld"
        verbose_name_plural = "Schulden"
        ordering = ['-due_date']
    
    def __str__(self):
        return f"Schuld {self.remaining_amount}€ - {self.parent.get_full_name()}"
    
    @property
    def days_overdue(self):
        """Количество дней просрочки"""
        if self.overdue_since:
            from datetime import date
            return (date.today() - self.overdue_since).days
        return 0
    
    def mark_as_resolved(self):
        """Отмечает задолженность как погашенную"""
        from datetime import date
        self.is_resolved = True
        self.resolved_date = date.today()
        self.remaining_amount = Decimal('0.00')
        self.save()


class PaymentPlan(models.Model):
    """Модель плана погашения задолженности"""
    
    debt = models.OneToOneField(
        Debt,
        on_delete=models.CASCADE,
        related_name='payment_plan',
        verbose_name="Schuld"
    )
    
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Gesamtbetrag"
    )
    monthly_payment = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        verbose_name="Monatliche Rate"
    )
    start_date = models.DateField(
        verbose_name="Startdatum"
    )
    end_date = models.DateField(
        verbose_name="Enddatum"
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktiv"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Erstellt am"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name="Erstellt von"
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name="Notizen"
    )
    
    class Meta:
        verbose_name = "Ratenzahlungsplan"
        verbose_name_plural = "Ratenzahlungsplaene"
    
    def __str__(self):
        return f"Ratenzahlung {self.monthly_payment}€/Monat - {self.debt.parent.get_full_name()}"


class PaymentPlanInstallment(models.Model):
    """Модель рассрочки платежа"""
    
    payment_plan = models.ForeignKey(
        PaymentPlan,
        on_delete=models.CASCADE,
        related_name='installments',
        verbose_name="Ratenzahlungsplan"
    )
    
    installment_number = models.IntegerField(
        verbose_name="Ratennummer"
    )
    due_date = models.DateField(
        verbose_name="Faelligkeitsdatum"
    )
    amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        verbose_name="Betrag"
    )
    
    is_paid = models.BooleanField(
        default=False,
        verbose_name="Bezahlt"
    )
    paid_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Zahlungsdatum"
    )
    paid_amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Bezahlter Betrag"
    )
    
    class Meta:
        verbose_name = "Rate"
        verbose_name_plural = "Raten"
        ordering = ['due_date']
        unique_together = ['payment_plan', 'installment_number']
    
    def __str__(self):
        return f"Rate {self.installment_number}: {self.amount}€"