from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from clients.models import UserProfile


class Command(BaseCommand):
    help = "Создает суперпользователя с профилем администратора"

    def add_arguments(self, parser):
        parser.add_argument("--username", type=str, help="Имя пользователя")
        parser.add_argument("--email", type=str, help="Email")
        parser.add_argument("--password", type=str, help="Пароль")

    def handle(self, *args, **options):
        username = options.get("username") or "admin"
        email = options.get("email") or "admin@bildungszentrum.de"
        password = options.get("password") or "admin123"

        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f"Пользователь {username} уже существует")
            )
            return

        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            first_name="Admin",
            last_name="Administrator",
        )

        UserProfile.objects.create(
            user=user,
            role="admin",
            phone="+49 30 12345678",
            address="Hauptstraße 1, 10115 Berlin",
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Суперпользователь {username} создан с профилем администратора"
            )
        )
        self.stdout.write(f"Логин: {username}")
        self.stdout.write(f"Пароль: {password}")
        self.stdout.write(f"Email: {email}")
