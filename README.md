# Бот для сбора заявок на работу (WB-Applications-TG-Bot)

Телеграм-бот для сбора и обработки заявок от пользователей с удобной админ-панелью для их модерации. Бот использует пошаговый опрос для сбора данных, позволяет пользователям редактировать свои заявки, а администраторам — эффективно управлять потоком поступающей информации.

## ✨ Основные возможности

### Для пользователей:
- **Подача заявки:** Пошаговый процесс заполнения анкеты (возраст, гражданство, регион, адрес, телефон).
- **Редактирование:** Возможность проверить и изменить любые данные перед финальной отправкой.
- **Обновление заявки:** Если у пользователя уже есть заявка, бот предложит обновить её или заполнить заново.
- **Отмена:** Возможность отменить процесс заполнения на любом этапе.
- **Уведомления:** Пользователь получает уведомления о статусе своей заявки (принята или отклонена с указанием причины).

### Для администраторов:
- **Уведомления в реальном времени:** Новые и обновленные заявки мгновенно присылаются в специальный администраторский чат.
- **Просмотр заявок:** Команда `/view_apps` открывает интерактивный список всех активных заявок с пагинацией.
- **Детальный просмотр:** Возможность открыть полную информацию по каждой заявке.
- **Управление заявками:**
    - ✅ **Принять:** Одобрить заявку (пользователь получит уведомление).
    - ❌ **Отклонить:** Отклонить заявку с обязательным указанием причины (пользователь получит уведомление с причиной).
    - ✍️ **Написать пользователю:** Отправить сообщение пользователю прямо из интерфейса просмотра заявки.
    - 🚫 **Заблокировать пользователя:** Забанить пользователя, чтобы он больше не мог взаимодействовать с ботом.

## ⚙️ Технический стек и особенности

- **Фреймворк:** [aiogram 3.x](https://github.com/aiogram/aiogram)
- **База данных:** SQLite (асинхронная работа через `aiosqlite`)
- **Конечные автоматы (FSM):** Для реализации пошагового сбора данных от пользователя.
- **Разделение логики:** Код четко разделен на обработчики для пользователей (`user_handlers`) и администраторов (`admin_handlers`), что упрощает поддержку.
- **Кастомные фильтры:** Фильтры для проверки прав администратора (`IsAdmin`) и статуса блокировки (`IsBanned`).
- **Middleware:** Используются для "проброса" зависимостей (например, ID админ-чата и экземпляра `BanManager`) в обработчики.
- **Кэширование:** Список заблокированных пользователей кэшируется в `set` при старте бота для мгновенной проверки без запросов к БД.

## 📂 Структура проекта

```
.
├── .gitignore
├── bot.py              # <-- Главный файл, точка входа, инициализация и запуск бота
├── data/
│   ├── bot_picture_greeting.jpg
│   └── database.db
├── logs/               # <-- Папка для лог-файлов
└── src/                # <-- Папка с исходным кодом
    ├── admin_handlers.py # <-- Логика для команд и действий администраторов
    ├── ban_manager.py    # <-- Класс для управления банами
    ├── config.py         # <-- Файл конфигурации (токен, ID админов, и т.д.)
    ├── database.py       # <-- Функции для работы с базой данных
    ├── filters.py        # <-- Пользовательские фильтры
    ├── keyboards.py      # <-- Функции для генерации клавиатур
    ├── middlewares.py    # <-- Пользовательские middleware
    ├── setup_logging.py  # <-- Настройка логирования
    └── user_handlers.py  # <-- Логика для взаимодействия с пользователями (FSM)
```

## 🚀 Установка и запуск

1.  **Клонируйте репозиторий:**
    ```bash
    git clone https://github.com/karriiiii/WB-Applications-Telegram-Bot
    cd WB-Applications-Telegram-Bot
    ```

2.  **Создайте и активируйте виртуальное окружение:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Для Windows: venv\Scripts\activate
    ```

3.  **Установите зависимости:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Настройте конфигурацию:**
    Откройте файл `config.py` и заполните необходимые переменные.

5.  **Запустите бота:**
    ```bash
    python bot.py
    ```

## 🔧 Конфигурация (`config.py`)

Перед запуском необходимо корректно заполнить файл `config.py`.

-   `BOT_TOKEN`: Токен вашего бота. Получите его у [@BotFather](https://t.me/BotFather) в Telegram.
    ```python
    BOT_TOKEN = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    ```

-   `ADMIN_CHAT_ID_STR`: ID чата (группы или канала), куда будут приходить уведомления о новых заявках.
    -   **Как получить?** Добавьте бота [@userinfobot](https://t.me/userinfobot) или [@getmyid_bot](https://t.me/getmyid_bot) в ваш чат, и он покажет ID чата. ID для групп обычно начинается с `-`.
    ```python
    ADMIN_CHAT_ID_STR = "-1001234567890"
    ```

-   `ADMIN_USER_IDS_STR`: Список числовых ID пользователей Telegram, которые будут иметь права администратора в боте. Указываются через запятую, без пробелов.
    -   **Как получить?** Напишите боту [@userinfobot](https://t.me/userinfobot) или [@getmyid_bot](https://t.me/getmyid_bot), и он покажет ваш User ID.
    ```python
    ADMIN_USER_IDS_STR = "987654321,123456789"
    ```

-   `GREETING_PICTURE_PATH`: Путь к картинке, которая будет отправляться с приветственным сообщением при команде `/start`.
    ```python
    GREETING_PICTURE_PATH = r'data/bot_picture_greeting.jpg'
    ```

-   Остальные параметры, как правило, не требуют изменений для стандартного запуска.
