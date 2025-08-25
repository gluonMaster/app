from django import template

register = template.Library()


@register.filter
def add_class(field, css_class):
    """
    Добавляет CSS класс к полю формы
    """
    if hasattr(field, "as_widget"):
        return field.as_widget(attrs={"class": css_class})
    return field
