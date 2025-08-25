from crispy_forms.bootstrap import InlineRadios
from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Column, Div, Layout, Row, Submit
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Child, UserProfile


class UserProfileForm(forms.ModelForm):
    """Форма для редактирования профиля пользователя"""

    class Meta:
        model = UserProfile
        fields = ["phone", "address", "birth_date", "iban", "bic", "bank_name"]
        widgets = {
            "birth_date": forms.DateInput(attrs={"type": "date"}),
            "address": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "phone": "Telefonnummer",
            "address": "Adresse",
            "birth_date": "Geburtsdatum",
            "iban": "IBAN",
            "bic": "BIC",
            "bank_name": "Bankname",
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column("phone", css_class="form-group col-md-6 mb-0"),
                Column("birth_date", css_class="form-group col-md-6 mb-0"),
                css_class="form-row",
            ),
            "address",
            HTML('<h5 class="mt-3">Bankdaten (nur für SEPA-Zahlungen)</h5>'),
            Row(
                Column("iban", css_class="form-group col-md-6 mb-0"),
                Column("bic", css_class="form-group col-md-6 mb-0"),
                css_class="form-row",
            ),
            "bank_name",
            Submit("submit", "Speichern", css_class="btn btn-primary"),
        )

        # Скрываем банковские поля если не SEPA клиент
        if self.instance and self.instance.user:
            contracts = self.instance.user.contracts.filter(
                payment_type="sepa", status="active"
            )
            if not contracts.exists():
                self.fields["iban"].widget.attrs[
                    "placeholder"
                ] = "Nur für SEPA-Kunden erforderlich"
                self.fields["bic"].widget.attrs[
                    "placeholder"
                ] = "Nur für SEPA-Kunden erforderlich"
                self.fields["bank_name"].widget.attrs[
                    "placeholder"
                ] = "Nur für SEPA-Kunden erforderlich"


class UserForm(forms.ModelForm):
    """Форма для редактирования основной информации пользователя"""

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]
        labels = {
            "first_name": "Vorname",
            "last_name": "Nachname",
            "email": "E-Mail",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column("first_name", css_class="form-group col-md-6 mb-0"),
                Column("last_name", css_class="form-group col-md-6 mb-0"),
                css_class="form-row",
            ),
            "email",
            Submit("submit", "Speichern", css_class="btn btn-primary"),
        )


class ChildForm(forms.ModelForm):
    """Форма для добавления/редактирования ребенка"""

    first_name = forms.CharField(label="Vorname", max_length=30)
    last_name = forms.CharField(label="Nachname", max_length=30)
    email = forms.EmailField(label="E-Mail (optional)", required=False)

    class Meta:
        model = Child
        fields = [
            "birth_date",
            "school_class",
            "medical_notes",
            "special_needs",
            "notes",
        ]
        widgets = {
            "birth_date": forms.DateInput(attrs={"type": "date"}),
            "medical_notes": forms.Textarea(attrs={"rows": 3}),
            "special_needs": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "birth_date": "Geburtsdatum",
            "school_class": "Schulklasse",
            "medical_notes": "Medizinische Hinweise",
            "special_needs": "Besondere Bedürfnisse",
            "notes": "Notizen",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML("<h5>Persönliche Daten</h5>"),
            Row(
                Column("first_name", css_class="form-group col-md-6 mb-0"),
                Column("last_name", css_class="form-group col-md-6 mb-0"),
                css_class="form-row",
            ),
            Row(
                Column("birth_date", css_class="form-group col-md-6 mb-0"),
                Column("school_class", css_class="form-group col-md-6 mb-0"),
                css_class="form-row",
            ),
            "email",
            HTML('<h5 class="mt-3">Zusätzliche Informationen</h5>'),
            "medical_notes",
            "special_needs",
            "notes",
            Submit("submit", "Speichern", css_class="btn btn-success"),
        )

        # Если редактируем существующего ребенка, заполняем поля User
        if self.instance and self.instance.user:
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name
            self.fields["email"].initial = self.instance.user.email

    def save(self, commit=True, parent=None):
        """Создает/обновляет и User, и Child"""
        child = super().save(commit=False)

        if not child.user_id:  # Новый ребенок
            # Создаем пользователя
            username = f"{self.cleaned_data['first_name'].lower()}.{self.cleaned_data['last_name'].lower()}"
            # Обеспечиваем уникальность username
            base_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1

            user = User.objects.create_user(
                username=username,
                first_name=self.cleaned_data["first_name"],
                last_name=self.cleaned_data["last_name"],
                email=self.cleaned_data["email"] or "",
                password="temp123",  # Временный пароль
            )

            # Создаем профиль ребенка
            UserProfile.objects.create(
                user=user, role="child", birth_date=self.cleaned_data["birth_date"]
            )

            child.user = user
            if parent:
                child.parent = parent
        else:
            # Обновляем существующего пользователя
            user = child.user
            user.first_name = self.cleaned_data["first_name"]
            user.last_name = self.cleaned_data["last_name"]
            user.email = self.cleaned_data["email"] or ""
            user.save()

        if commit:
            child.save()

        return child
