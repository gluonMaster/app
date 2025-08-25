FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/home/app/.local/bin:$PATH"

WORKDIR /app

# Системные пакеты
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    git openssh-client ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# (новое) Создаём пользователя 'app' заранее
RUN useradd -m app

# Зависимости Python
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Код приложения
COPY . .

# Права на каталог проекта
RUN mkdir -p /app/static && chown -R app:app /app

USER app

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]