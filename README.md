# Бот для организации тех. поддержки на базе форум-топиков в чате Telegram

## Установка

1. Установить Python 3.10(С другими версиями не работает)
2. Установить зависимости: `pip install -r requirements.txt`
3. Заполнить файл .env (см. ниже)

```.env
BOT_TOKEN=Токен бота
SUPPORT_CHAT_ID=ID чата с поддержкой
```

4. Запустить бота: `python main.py`
5. Добавить бота в ваш чат
   6. Дать боту права администратора
   7. Убедиться, что в чате включены темы
