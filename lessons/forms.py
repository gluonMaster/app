from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Column, Field, Layout, Row, Submit
from django import forms

from clients.models import Child

from .models import ActualLesson, AttendanceRecord, Group, Subject, TrialLesson


class ActualLessonForm(forms.ModelForm):
    """Форма для обновления содержания проведенного занятия"""

    class Meta:
        model = ActualLesson
        fields = ["lesson_content", "homework_assigned", "notes", "duration"]
        widgets = {
            "lesson_content": forms.Textarea(attrs={"rows": 4}),
            "homework_assigned": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }
        labels = {
            "lesson_content": "Unterrichtsinhalt",
            "homework_assigned": "Hausaufgaben",
            "notes": "Notizen",
            "duration": "Tatsächliche Dauer (Minuten)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.layout = Layout(
            "lesson_content",
            "homework_assigned",
            Row(
                Column("duration", css_class="form-group col-md-6 mb-0"),
                css_class="form-row",
            ),
            "notes",
            Submit("submit", "Speichern", css_class="btn btn-primary"),
        )


class LessonAttendanceForm(forms.Form):
    """Форма для отметки посещаемости занятия"""

    lesson_content = forms.CharField(
        label="Unterrichtsinhalt",
        widget=forms.Textarea(attrs={"rows": 4}),
        required=False,
    )
    homework_assigned = forms.CharField(
        label="Hausaufgaben", widget=forms.Textarea(attrs={"rows": 3}), required=False
    )
    notes = forms.CharField(
        label="Notizen", widget=forms.Textarea(attrs={"rows": 2}), required=False
    )

    def __init__(self, *args, **kwargs):
        self.lesson = kwargs.pop("lesson", None)
        super().__init__(*args, **kwargs)

        if self.lesson:
            # Добавляем поля для каждого зачисленного студента
            enrolled_students = self.lesson.group.groupenrollment_set.filter(
                status="active"
            )

            for enrollment in enrolled_students:
                child = enrollment.child

                # Поле статуса посещаемости
                self.fields[f"attendance_{child.id}"] = forms.ChoiceField(
                    label=f"{child.user.get_full_name()}",
                    choices=AttendanceRecord.ATTENDANCE_STATUS,
                    initial="present",
                    widget=forms.Select(attrs={"class": "form-control"}),
                )

                # Поле времени прихода
                self.fields[f"arrival_time_{child.id}"] = forms.TimeField(
                    label="Ankunftszeit",
                    required=False,
                    widget=forms.TimeInput(
                        attrs={"type": "time", "class": "form-control"}
                    ),
                )

                # Поле времени ухода
                self.fields[f"departure_time_{child.id}"] = forms.TimeField(
                    label="Abgangszeit",
                    required=False,
                    widget=forms.TimeInput(
                        attrs={"type": "time", "class": "form-control"}
                    ),
                )

                # Поле заметок о студенте
                self.fields[f"notes_{child.id}"] = forms.CharField(
                    label="Notizen",
                    required=False,
                    widget=forms.TextInput(attrs={"class": "form-control"}),
                )

        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            HTML("<h5>Unterrichtsinhalt</h5>"),
            "lesson_content",
            "homework_assigned",
            "notes",
            HTML('<h5 class="mt-4">Anwesenheit</h5>'),
            HTML('<div class="table-responsive"><table class="table table-striped">'),
            HTML(
                "<thead><tr><th>Schüler</th><th>Status</th><th>Ankunft</th><th>Abgang</th><th>Notizen</th></tr></thead>"
            ),
            HTML("<tbody>"),
        )

        if self.lesson:
            enrolled_students = self.lesson.group.groupenrollment_set.filter(
                status="active"
            )
            for enrollment in enrolled_students:
                child = enrollment.child
                self.helper.layout.append(
                    HTML(
                        f"""
                    <tr>
                        <td><strong>{child.user.get_full_name()}</strong></td>
                        <td>{{% field 'attendance_{child.id}' %}}</td>
                        <td>{{% field 'arrival_time_{child.id}' %}}</td>
                        <td>{{% field 'departure_time_{child.id}' %}}</td>
                        <td>{{% field 'notes_{child.id}' %}}</td>
                    </tr>
                    """
                    )
                )

        self.helper.layout.extend(
            [
                HTML("</tbody></table></div>"),
                Submit(
                    "submit",
                    "Anwesenheit speichern",
                    css_class="btn btn-success btn-lg",
                ),
            ]
        )


class TrialLessonBookingForm(forms.ModelForm):
    """Форма для записи на пробное занятие"""

    class Meta:
        model = TrialLesson
        fields = ["child", "subject", "scheduled_date", "notes"]
        widgets = {
            "scheduled_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "child": "Kind",
            "subject": "Fach",
            "scheduled_date": "Gewünschtes Datum und Uhrzeit",
            "notes": "Besondere Wünsche/Notizen",
        }

    def __init__(self, *args, **kwargs):
        self.parent = kwargs.pop("parent", None)
        super().__init__(*args, **kwargs)

        if self.parent:
            self.fields["child"].queryset = Child.objects.filter(
                parent=self.parent, is_active=True
            )

        self.fields["subject"].queryset = Subject.objects.filter(is_active=True)

        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML(
                '<div class="alert alert-info">Probestunden sind kostenlos und dauern 45 Minuten.</div>'
            ),
            Row(
                Column("child", css_class="form-group col-md-6 mb-0"),
                Column("subject", css_class="form-group col-md-6 mb-0"),
                css_class="form-row",
            ),
            "scheduled_date",
            "notes",
            Submit("submit", "Probestunde buchen", css_class="btn btn-success"),
        )
