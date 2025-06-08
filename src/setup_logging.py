# --- НАСТРОЙКА ЛОГИРОВАНИЯ ---
import logging
import sys
from logging.handlers import RotatingFileHandler
import os
from datetime import datetime

def setup_logger():
    log_level = logging.INFO
    log_folder = "logs"

    # Создаем папку для логов, если ее нет
    os.makedirs(log_folder, exist_ok=True)

    # Генерируем имя файла лога с текущей датой и временем
    # Например: 20231026_143000_bot.log
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file_path = os.path.join(log_folder, f"{timestamp}_bot.log")

    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Форматтер для логов
    log_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)-8s - %(name)-25s - %(module)s.%(funcName)s:%(lineno)d - %(message)s"
    )

    # Обработчик для вывода в консоль
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)

    # Обработчик для записи в файл с ротацией
    # maxBytes - максимальный размер файла (5 MB)
    # backupCount - сколько старых файлов хранить (5 файлов: bot.log, bot.log.1, bot.log.2, ...)
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(log_formatter)

    # Очищаем существующие обработчики, чтобы избежать дублирования (если были от basicConfig)
    if logger.hasHandlers():
        logger.handlers.clear()
        
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)