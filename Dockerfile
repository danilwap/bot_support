# Используем базовый образ с Python 3.10
FROM python:3.10

# Копируем файлы проекта в корень контейнера
COPY . /

# Устанавливаем зависимости из файла requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Запускаем бота
CMD ["python", "/main.py"]