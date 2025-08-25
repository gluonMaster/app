# clients/django_stubs.pyi
# Типизация для Django моделей

from typing import Any

from django.contrib.auth.models import User
from django.db import models

# Расширяем User модель
class UserProfileMixin:
    userprofile: "UserProfile"
    contracts: models.Manager["Contract"]
    children: models.Manager["Child"]
    change_requests: models.Manager["ContractChangeRequest"]
    one_time_charges: models.Manager["OneTimeCharge"]
    invoices: models.Manager["Invoice"]
    debts: models.Manager["Debt"]
    notifications: models.Manager["Notification"]

# Добавляем методы к моделям
class UserProfile:
    def get_role_display(self) -> str: ...
    contracts: models.Manager[Any]

class Child:
    groupenrollment_set: models.Manager["GroupEnrollment"]
    absence_history: models.Manager["AbsenceHistory"]

class Contract:
    items: models.Manager["ContractItem"]
    change_requests: models.Manager["ContractChangeRequest"]

class Group:
    schedules: models.Manager["Schedule"]
    groupenrollment_set: models.Manager["GroupEnrollment"]
    actuallesson_set: models.Manager["ActualLesson"]

class Subject:
    group_set: models.Manager["Group"]
    pricelist_set: models.Manager["PriceList"]

class ActualLesson:
    attendance_records: models.Manager["AttendanceRecord"]
