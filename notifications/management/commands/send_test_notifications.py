import random

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from notifications.models import Notification


class Command(BaseCommand):
    help = "Отправляет тестовые уведомления пользователям"

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=10,
            help="Количество уведомлений для создания",
        )

    def handle(self, *args, **options):
        users = User.objects.filter(
            is_active=True, userprofile__role__in=["parent", "teacher"]
        )

        notification_templates = [
            {
                "type": "contract_change",
                "priority": "high",
                "title": "Vertragsaenderung",
                "message": "Ihr Vertrag wurde erfolgreich aktualisiert. Bitte pruefen Sie die neuen Konditionen.",
            },
            {
                "type": "schedule_change",
                "priority": "normal",
                "title": "Stundenplanaenderung",
                "message": "Der Stundenplan fuer die Mathematik-Gruppe wurde geaendert. Neue Zeit: Mittwoch 16:00.",
            },
            {
                "type": "absence_alert",
                "priority": "normal",
                "title": "Fehlzeit",
                "message": "Ihr Kind war heute nicht im Unterricht. Bitte entschuldigen Sie das Fehlen.",
            },
            {
                "type": "sepa_important",
                "priority": "critical",
                "title": "WICHTIG: SEPA-Mandat",
                "message": "Ihr SEPA-Mandat läuft ab. Bitte erneuern Sie es bis zum Monatsende.",
                "requires_acknowledgment": True,
            },
        ]

        created = 0
        for _ in range(options["count"]):
            user = random.choice(users)
            template = random.choice(notification_templates)

            Notification.objects.create(
                recipient=user,
                notification_type=template["type"],
                priority=template["priority"],
                title=template["title"],
                message=template["message"],
                requires_acknowledgment=template.get("requires_acknowledgment", False),
                is_important=template["priority"] in ["high", "critical"],
            )
            created += 1

        self.stdout.write(
            self.style.SUCCESS(f"✓ Создано {created} тестовых уведомлений")
        )
