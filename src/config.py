# ВАЖНО: Этот файл содержит конфигурацию.
# Не храните реальные значения (токены, ID) в этом файле в публичных репозиториях.

# --- ОСНОВНЫЕ ДАННЫЕ ---

# Токен вашего бота, полученный от @BotFather
BOT_TOKEN = "YOUR_BOT_TOKEN"

# ID чата (канала или группы), куда должны приходить уведомления о новых заявках.
# ID должен быть в виде строки. Для групп и каналов он обычно начинается с "-".
ADMIN_CHAT_ID_STR = "YOUR_ADMIN_CHAT_ID"

# Список числовых ID пользователей Telegram, которые являются администраторами.
# Указывайте через запятую, без пробелов. Пример: "12345678,87654321"
ADMIN_USER_IDS_STR = "YOUR_ADMIN_ID_1,YOUR_ADMIN_ID_2"


# --- ОБЩИЕ НАСТРОЙКИ ---

# Путь к файлу базы данных
DATABASE_FILE = r"data/database.db"

# Путь к приветственной картинке для команды /start
GREETING_PICTURE_PATH = r'data/bot_picture_greeting.jpg'

# Количество заявок, отображаемое на одной странице в админ-панели
APPLICATIONS_PER_PAGE = 5


# --- КОМАНДЫ БОТА ---
# Этот блок можно не менять. Он определяет меню команд, видимое пользователям.
from aiogram.types import BotCommand

DEFAULT_BOT_COMMANDS = [
    BotCommand(command="start", description="Начать/перезапустить бота"),
    BotCommand(command="cancel", description="Отменить текущее действие"),
    # Команды ниже будут работать только у админов, но видны всем в меню
    BotCommand(command="view_apps", description="Просмотреть заявки (только для админов)"),
    BotCommand(command="cancel_admin_action", description="Отменить текущее действие админа (только для админов)"),
]
