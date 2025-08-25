import random
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils.crypto import get_random_string

from clients.models import Child, UserProfile
from contracts.models import (
    Contract,
    ContractChangeRequest,
    ContractItem,
    Discount,
    DiscountType,
    PriceList,
)
from lessons.models import Group, GroupEnrollment, Schedule, Subject, TrialLesson
from notifications.models import Notification


class Command(BaseCommand):
    help = "Создает тестовые данные для системы управления учебным центром"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Очищает существующие данные перед созданием новых",
        )
        parser.add_argument(
            "--users",
            type=int,
            default=20,
            help="Количество тестовых пользователей для создания",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            self.stdout.write(self.style.WARNING("Очистка существующих данных..."))
            self.clear_data()

        self.stdout.write(self.style.SUCCESS("Создание базовых данных..."))
        self.create_base_data()

        self.stdout.write(self.style.SUCCESS("Создание тестовых пользователей..."))
        self.create_test_users(options["users"])

        self.stdout.write(self.style.SUCCESS("Создание тестовых контрактов..."))
        self.create_test_contracts()

        self.stdout.write(self.style.SUCCESS("Создание тестовых заявок..."))
        self.create_test_requests()

        self.stdout.write(self.style.SUCCESS("Создание тестовых занятий..."))
        self.create_test_lessons()

        self.stdout.write(self.style.SUCCESS("✅ Тестовые данные успешно созданы!"))

    def clear_data(self):
        """Очищает существующие тестовые данные"""
        # Удаляем все кроме суперпользователя
        User.objects.filter(is_superuser=False).delete()
        Subject.objects.all().delete()
        DiscountType.objects.all().delete()
        Notification.objects.all().delete()

    def create_base_data(self):
        """Создает базовые данные системы"""

        # Создаем предметы
        subjects_data = [
            {
                "name": "Mathematik",
                "code": "MATH",
                "default_duration": 45,
                "min_age": 6,
                "max_age": 18,
            },
            {
                "name": "Deutsch",
                "code": "DE",
                "default_duration": 45,
                "min_age": 6,
                "max_age": 18,
            },
            {
                "name": "Englisch",
                "code": "EN",
                "default_duration": 45,
                "min_age": 8,
                "max_age": 18,
            },
            {
                "name": "Russisch",
                "code": "RU",
                "default_duration": 45,
                "min_age": 10,
                "max_age": 18,
            },
            {
                "name": "Franzosisch",
                "code": "FR",
                "default_duration": 45,
                "min_age": 10,
                "max_age": 18,
            },
            {
                "name": "Physik",
                "code": "PHY",
                "default_duration": 60,
                "min_age": 12,
                "max_age": 18,
            },
            {
                "name": "Chemie",
                "code": "CHEM",
                "default_duration": 60,
                "min_age": 14,
                "max_age": 18,
            },
            {
                "name": "Informatik",
                "code": "INFO",
                "default_duration": 90,
                "min_age": 10,
                "max_age": 18,
            },
        ]

        subjects = []
        for subject_data in subjects_data:
            subject, created = Subject.objects.get_or_create(**subject_data)
            subjects.append(subject)

            # Создаем цены для предметов
            PriceList.objects.get_or_create(
                subject=subject,
                price_per_hour=Decimal(str(random.uniform(15.0, 35.0))),
                valid_from=date.today() - timedelta(days=30),
                created_by=User.objects.filter(is_superuser=True).first(),
                defaults={"is_active": True},
            )

        # Создаем типы скидок
        discount_types_data = [
            {
                "name": "Familienrabatt",
                "description": "Rabatt für Familien mit mehreren Kindern",
                "is_percentage": True,
            },
            {
                "name": "Mengenrabatt",
                "description": "Rabatt bei mehreren Fächern",
                "is_percentage": True,
            },
            {
                "name": "Sozialrabatt",
                "description": "Sozialrabatt für einkommensschwache Familien",
                "is_percentage": True,
            },
            {
                "name": "Frühbucherrabatt",
                "description": "Rabatt bei frühzeitiger Anmeldung",
                "is_percentage": False,
            },
        ]

        for discount_type_data in discount_types_data:
            discount_type, created = DiscountType.objects.get_or_create(
                **discount_type_data
            )

            # Создаем скидки
            if discount_type.name == "Familienrabatt":
                Discount.objects.get_or_create(
                    discount_type=discount_type,
                    condition_description="Ab 2 Kindern in der Familie",
                    value=Decimal("10.0"),
                    valid_from=date.today(),
                    applies_to_family=True,
                    defaults={"is_active": True},
                )
            elif discount_type.name == "Mengenrabatt":
                Discount.objects.get_or_create(
                    discount_type=discount_type,
                    condition_description="Ab 3 Fächern pro Kind",
                    value=Decimal("15.0"),
                    valid_from=date.today(),
                    min_subjects=3,
                    defaults={"is_active": True},
                )

        self.stdout.write(f"✓ Создано {len(subjects)} предметов и скидки")

    def create_test_users(self, count):
        """Создает тестовых пользователей"""

        # Немецкие имена для тестирования
        first_names = [
            "Hans",
            "Anna",
            "Klaus",
            "Maria",
            "Peter",
            "Sabine",
            "Michael",
            "Petra",
            "Wolfgang",
            "Monika",
        ]
        last_names = [
            "Mueller",
            "Schmidt",
            "Schneider",
            "Fischer",
            "Weber",
            "Meyer",
            "Wagner",
            "Becker",
            "Schulz",
            "Hoffmann",
        ]
        child_names = [
            "Max",
            "Emma",
            "Leon",
            "Mia",
            "Paul",
            "Hannah",
            "Felix",
            "Lea",
            "Jonas",
            "Lina",
        ]

        # Создаем учителей
        for i in range(3):
            user = User.objects.create_user(
                username=f"teacher{i+1}",
                email=f"teacher{i+1}@bildungszentrum.de",
                first_name=random.choice(first_names),
                last_name=random.choice(last_names),
                password="teacher123",
            )

            UserProfile.objects.create(
                user=user,
                role="teacher",
                phone=f"+49 30 {random.randint(1000000, 9999999)}",
                address=f"Musterstraße {random.randint(1, 100)}, 10115 Berlin",
                specialization=f'Spezialist für {random.choice(["Mathematik", "Sprachen", "Naturwissenschaften"])}',
                hire_date=date.today() - timedelta(days=random.randint(30, 1000)),
            )

        # Создаем бухгалтеров
        for i in range(2):
            user = User.objects.create_user(
                username=f"accountant{i+1}",
                email=f"buchhalter{i+1}@bildungszentrum.de",
                first_name=random.choice(first_names),
                last_name=random.choice(last_names),
                password="accountant123",
            )

            UserProfile.objects.create(
                user=user,
                role="accountant",
                phone=f"+49 30 {random.randint(1000000, 9999999)}",
                address=f"Musterstraße {random.randint(1, 100)}, 10115 Berlin",
            )

        # Создаем администратора (если не существует)
        if not User.objects.filter(username="admin_test").exists():
            admin_user = User.objects.create_user(
                username="admin_test",
                email="admin_test@bildungszentrum.de",
                first_name="Admin",
                last_name="Test",
                password="admin123",
            )

            UserProfile.objects.create(
                user=admin_user,
                role="admin",
                phone="+49 30 12345678",
                address="Hauptstraße 1, 10115 Berlin",
            )

        # Создаем родителей и детей
        parents_created = 0
        children_created = 0

        for i in range(min(count, 15)):  # Максимум 15 семей
            # Создаем родителя
            parent_user = User.objects.create_user(
                username=f"parent{i+1}",
                email=f"parent{i+1}@example.com",
                first_name=random.choice(first_names),
                last_name=random.choice(last_names),
                password="parent123",
            )

            payment_types = ["self", "sepa", "jobcenter"]
            payment_type = random.choice(payment_types)

            parent_profile = UserProfile.objects.create(
                user=parent_user,
                role="parent",
                phone=f"+49 30 {random.randint(1000000, 9999999)}",
                address=f'{random.choice(["Berliner Straße", "Hauptstraße", "Lindenstraße"])} {random.randint(1, 200)}, 10115 Berlin',
                birth_date=date(
                    random.randint(1970, 1990),
                    random.randint(1, 12),
                    random.randint(1, 28),
                ),
                iban=(
                    f"DE{random.randint(10, 99)} 1234 5678 {random.randint(1000, 9999)} {random.randint(100000, 999999)}"
                    if payment_type == "sepa"
                    else ""
                ),
                bic="DEUTDEDB123" if payment_type == "sepa" else "",
                bank_name="Deutsche Bank" if payment_type == "sepa" else "",
            )
            parents_created += 1

            # Создаем 1-3 детей для каждого родителя
            num_children = random.randint(1, 3)
            for j in range(num_children):
                child_user = User.objects.create_user(
                    username=f"child{i+1}_{j+1}",
                    email=f"child{i+1}_{j+1}@example.com",
                    first_name=random.choice(child_names),
                    last_name=parent_user.last_name,
                    password="child123",
                )

                # Возраст от 6 до 17 лет
                age = random.randint(6, 17)
                birth_year = date.today().year - age

                Child.objects.create(
                    user=child_user,
                    parent=parent_user,
                    birth_date=date(
                        birth_year, random.randint(1, 12), random.randint(1, 28)
                    ),
                    school_class=f"{random.randint(1, 12)}. Klasse",
                    notes=f'Testschüler für {random.choice(["Mathematik", "Sprachen", "Naturwissenschaften"])}',
                )

                UserProfile.objects.create(
                    user=child_user,
                    role="child",
                    birth_date=date(
                        birth_year, random.randint(1, 12), random.randint(1, 28)
                    ),
                )
                children_created += 1

        self.stdout.write(
            f"✓ Создано {parents_created} родителей и {children_created} детей"
        )

    def create_test_contracts(self):
        """Создает тестовые контракты"""
        parents = User.objects.filter(userprofile__role="parent")
        subjects = Subject.objects.all()

        contracts_created = 0
        for parent in parents[:10]:  # Создаем контракты для первых 10 родителей
            children = Child.objects.filter(parent=parent)
            if not children:
                continue

            # Создаем контракт
            contract_number = f"V{date.today().year}{random.randint(1000, 9999)}"
            contract_type = random.choice(["monthly", "yearly", "nachhilfe"])
            payment_type = random.choice(["self", "sepa", "jobcenter"])

            contract = Contract.objects.create(
                contract_number=contract_number,
                parent=parent,
                contract_type=contract_type,
                payment_type=payment_type,
                status="active",
                start_date=date.today() - timedelta(days=random.randint(30, 200)),
                end_date=date.today() + timedelta(days=random.randint(200, 400)),
                cancellation_deadline=date.today()
                + timedelta(days=random.randint(30, 90)),
                created_by=User.objects.filter(userprofile__role="admin").first(),
            )

            # Добавляем позиции контракта
            for child in children:
                # Каждый ребенок изучает 1-3 предмета
                child_subjects = random.sample(list(subjects), random.randint(1, 3))

                for subject in child_subjects:
                    price_list = PriceList.objects.filter(
                        subject=subject, is_active=True
                    ).first()
                    if price_list:
                        ContractItem.objects.create(
                            contract=contract,
                            child=child,
                            subject=subject,
                            base_price=price_list.price_per_hour,
                            price_date=price_list.valid_from,
                            final_price=price_list.price_per_hour
                            * Decimal("0.9"),  # С небольшой скидкой
                            payer=random.choice(["client", "jobcenter"]),
                            hours_per_month=random.choice([4, 6, 8]),
                        )

            contracts_created += 1

        self.stdout.write(f"✓ Создано {contracts_created} контрактов")

    def create_test_requests(self):
        """Создает тестовые заявки на изменение контрактов"""
        parents = User.objects.filter(userprofile__role="parent")
        subjects = Subject.objects.all()

        requests_created = 0
        for parent in random.sample(
            list(parents), min(5, len(parents))
        ):  # 5 случайных родителей
            children = Child.objects.filter(parent=parent)
            if not children:
                continue

            contract = Contract.objects.filter(parent=parent, status="active").first()
            child = random.choice(children)
            subject = random.choice(subjects)

            request_type = random.choice(
                ["add_subject", "remove_subject", "change_schedule"]
            )

            ContractChangeRequest.objects.create(
                contract=contract,
                parent=parent,
                child=child,
                request_type=request_type,
                subject=(
                    subject
                    if request_type in ["add_subject", "remove_subject"]
                    else None
                ),
                status=random.choice(["pending", "approved", "rejected"]),
                description=f"Antrag auf {request_type} für {child.user.get_full_name()}",
                parent_reason="Test-Begründung für die Änderung",
                requested_start_date=date.today()
                + timedelta(days=random.randint(7, 30)),
                estimated_monthly_change=Decimal(str(random.uniform(-50.0, 100.0))),
            )
            requests_created += 1

        self.stdout.write(f"✓ Создано {requests_created} заявок на изменение")

    def create_test_lessons(self):
        """Создает тестовые группы и занятия"""
        subjects = Subject.objects.all()
        teachers = User.objects.filter(userprofile__role="teacher")
        children = Child.objects.all()

        groups_created = 0
        for subject in subjects:
            # Создаем 1-2 группы для каждого предмета
            for i in range(random.randint(1, 2)):
                group_name = f"{subject.name} Gruppe {i+1}"
                group_type = random.choice(["group", "individual"])

                group = Group.objects.create(
                    name=group_name,
                    subject=subject,
                    group_type=group_type,
                    level=random.choice(
                        ["Anfaenger", "Fortgeschrittene", "Mittelstufe"]
                    ),
                    max_students=(
                        1 if group_type == "individual" else random.randint(8, 15)
                    ),
                )

                # Добавляем учителей
                group.teachers.add(random.choice(teachers))

                # Создаем расписание
                weekday = random.randint(0, 4)  # Понедельник-пятница
                start_hour = random.randint(14, 18)  # 14:00-18:00

                Schedule.objects.create(
                    group=group,
                    weekday=weekday,
                    start_time=f"{start_hour}:00",
                    duration=subject.default_duration,
                    valid_from=date.today() - timedelta(days=30),
                    classroom=f"Raum {random.randint(101, 210)}",
                )

                # Зачисляем детей в группы
                available_children = [
                    child
                    for child in children
                    if child.age >= (subject.min_age or 0)
                    and child.age <= (subject.max_age or 18)
                ]

                enrolled_count = min(
                    group.max_students, len(available_children), random.randint(3, 8)
                )
                enrolled_children = random.sample(available_children, enrolled_count)

                for child in enrolled_children:
                    # Находим контракт ребенка с этим предметом
                    contract_item = ContractItem.objects.filter(
                        child=child, subject=subject, is_active=True
                    ).first()

                    if contract_item:
                        GroupEnrollment.objects.create(
                            child=child,
                            group=group,
                            contract_item=contract_item,
                            enrollment_date=date.today()
                            - timedelta(days=random.randint(7, 60)),
                        )

                groups_created += 1

        self.stdout.write(f"✓ Создано {groups_created} учебных групп")
