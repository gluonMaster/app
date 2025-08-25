from crispy_forms.bootstrap import InlineRadios
from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Column, Div, Field, Layout, Row, Submit
from django import forms
from django.contrib.auth.models import User

from clients.models import Child
from lessons.models import Subject

from .models import Contract, ContractChangeRequest, OneTimeCharge


class ContractChangeRequestForm(forms.ModelForm):
    """Форма для создания заявки на изменение контракта"""

    class Meta:
        model = ContractChangeRequest
        fields = [
            "contract",
            "child",
            "request_type",
            "subject",
            "requested_start_date",
            "description",
            "parent_reason",
        ]
        widgets = {
            "requested_start_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 4}),
            "parent_reason": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "contract": "Vertrag",
            "child": "Kind",
            "request_type": "Art der Änderung",
            "subject": "Fach",
            "requested_start_date": "Gewünschtes Startdatum",
            "description": "Beschreibung der Änderung",
            "parent_reason": "Begründung",
        }

    def __init__(self, *args, **kwargs):
        self.parent = kwargs.pop("parent", None)
        super().__init__(*args, **kwargs)

        if self.parent:
            # Фильтруем контракты родителя
            self.fields["contract"].queryset = Contract.objects.filter(
                parent=self.parent, status="active"
            )

            # Фильтруем детей родителя
            self.fields["child"].queryset = Child.objects.filter(
                parent=self.parent, is_active=True
            )

        # Все активные предметы
        self.fields["subject"].queryset = Subject.objects.filter(is_active=True)

        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML(
                '<div class="alert alert-info">Bitte füllen Sie alle relevanten Felder aus. Ihre Anfrage wird von unseren Administratoren geprüft.</div>'
            ),
            Row(
                Column("contract", css_class="form-group col-md-6 mb-0"),
                Column("child", css_class="form-group col-md-6 mb-0"),
                css_class="form-row",
            ),
            Row(
                Column("request_type", css_class="form-group col-md-6 mb-0"),
                Column("subject", css_class="form-group col-md-6 mb-0"),
                css_class="form-row",
            ),
            "requested_start_date",
            "description",
            "parent_reason",
            HTML(
                '<div id="price-estimate" class="alert alert-secondary mt-3" style="display: none;"></div>'
            ),
            Submit("submit", "Antrag einreichen", css_class="btn btn-primary"),
        )

        # Добавляем JavaScript для динамического расчета стоимости
        self.helper.layout.append(
            HTML(
                """
            <script>
            document.addEventListener('DOMContentLoaded', function() {
                const requestType = document.getElementById('id_request_type');
                const subject = document.getElementById('id_subject');
                const child = document.getElementById('id_child');
                const priceEstimate = document.getElementById('price-estimate');

                function updateEstimate() {
                    if (requestType.value && subject.value) {
                        fetch(`/contracts/ajax/calculate-price/?request_type=${requestType.value}&subject_id=${subject.value}&child_id=${child.value}`)
                            .then(response => response.json())
                            .then(data => {
                                if (data.formatted_change) {
                                    priceEstimate.innerHTML = `<strong>Geschätzte monatliche Änderung:</strong> ${data.formatted_change}`;
                                    priceEstimate.style.display = 'block';
                                }
                            });
                    }
                }

                requestType.addEventListener('change', updateEstimate);
                subject.addEventListener('change', updateEstimate);
                child.addEventListener('change', updateEstimate);
            });
            </script>
            """
            )
        )

    def clean(self):
        cleaned_data = super().clean()
        request_type = cleaned_data.get("request_type")
        subject = cleaned_data.get("subject")
        child = cleaned_data.get("child")
        contract = cleaned_data.get("contract")

        # Валидация в зависимости от типа заявки
        if request_type in ["add_subject", "remove_subject"] and not subject:
            raise forms.ValidationError(
                "Для этого типа заявки необходимо выбрать предмет."
            )

        if request_type == "remove_subject" and subject and child:
            # Проверяем, что ребенок действительно изучает этот предмет
            from .models import ContractItem

            existing_item = ContractItem.objects.filter(
                contract=contract, child=child, subject=subject, is_active=True
            ).exists()

            if not existing_item:
                raise forms.ValidationError(
                    "Этот ребенок не изучает выбранный предмет."
                )

        return cleaned_data


class OneTimeChargeForm(forms.ModelForm):
    """Форма для создания разового начисления"""

    class Meta:
        model = OneTimeCharge
        fields = ["child", "charge_type", "description", "amount", "due_date", "notes"]
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "amount": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }
        labels = {
            "child": "Kind (optional)",
            "charge_type": "Art der Gebühr",
            "description": "Beschreibung",
            "amount": "Betrag (€)",
            "due_date": "Fälligkeitsdatum",
            "notes": "Notizen",
        }

    def __init__(self, *args, **kwargs):
        self.parent = kwargs.pop("parent", None)
        super().__init__(*args, **kwargs)

        if self.parent:
            self.fields["child"].queryset = Child.objects.filter(
                parent=self.parent, is_active=True
            )

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column("charge_type", css_class="form-group col-md-6 mb-0"),
                Column("child", css_class="form-group col-md-6 mb-0"),
                css_class="form-row",
            ),
            "description",
            Row(
                Column("amount", css_class="form-group col-md-6 mb-0"),
                Column("due_date", css_class="form-group col-md-6 mb-0"),
                css_class="form-row",
            ),
            "notes",
            Submit("submit", "Gebühr erstellen", css_class="btn btn-success"),
        )
