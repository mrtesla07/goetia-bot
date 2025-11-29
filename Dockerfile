FROM python:3.11-slim

WORKDIR /app

# Установим зависимости системы (если появятся, можно добавить)
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем зависимости проекта. Код монтируется с хоста, поэтому копируем только requirements.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Код и данные будут примонтированы volume-ами, поэтому на уровне образа ничего не копируем.
CMD ["python", "main.py"]
