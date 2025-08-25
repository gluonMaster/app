from datetime import datetime, timedelta

from django import template

register = template.Library()


@register.filter
def addtime(time_obj, duration):
    """
    Добавляет duration (в минутах) к time объекту
    """
    if not time_obj or not duration:
        return time_obj

    # Создаем datetime объект из time
    dt = datetime.combine(datetime.today(), time_obj)
    # Добавляем duration в минутах
    dt_new = dt + timedelta(minutes=duration)
    # Возвращаем только время
    return dt_new.time()


@register.filter
def add_class(field, css_class):
    """
    Добавляет CSS класс к полю формы
    """
    if hasattr(field, "as_widget"):
        return field.as_widget(attrs={"class": css_class})
    return field
