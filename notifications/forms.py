from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Column, Layout, Row, Submit
from django import forms
from django.contrib.auth.models import User

from .models import Notification


class SendNotificationForm(forms.ModelForm):
    """Форма для отправки уведомления администраторами"""

    recipients = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        label="Empfänger",
    )

    class Meta:
        model = Notification
        fields = [
            "notification_type",
            "priority",
            "title",
            "message",
            "is_important",
            "requires_acknowledgment",
        ]
        widgets = {
            "message": forms.Textarea(attrs={"rows": 5}),
        }
        labels = {
            "notification_type": "Typ",
            "priority": "Priorität",
            "title": "Titel",
            "message": "Nachricht",
            "is_important": "Als wichtig markieren",
            "requires_acknowledgment": "Bestätigung erforderlich",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Фильтруем получателей по ролям
        self.fields["recipients"].queryset = User.objects.filter(
            is_active=True, userprofile__role__in=["parent", "child", "teacher"]
        ).select_related("userprofile")

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column("notification_type", css_class="form-group col-md-6 mb-0"),
                Column("priority", css_class="form-group col-md-6 mb-0"),
                css_class="form-row",
            ),
            "title",
            "message",
            Row(
                Column("is_important", css_class="form-group col-md-6 mb-0"),
                Column("requires_acknowledgment", css_class="form-group col-md-6 mb-0"),
                css_class="form-row",
            ),
            HTML("<h5>Empfänger auswählen</h5>"),
            "recipients",
            Submit("submit", "Benachrichtigung senden", css_class="btn btn-primary"),
        )
