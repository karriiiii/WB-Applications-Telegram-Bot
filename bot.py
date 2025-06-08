import asyncio
import logging

from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove, BotCommandScopeAllPrivateChats
from aiogram.enums import ChatType

from src.setup_logging import setup_logger
from src.config import BOT_TOKEN, ADMIN_CHAT_ID_STR, ADMIN_USER_IDS_STR, DEFAULT_BOT_COMMANDS, GREETING_PICTURE_PATH
from src.middlewares import AdminChatIdMiddleware, BanManagerMiddleware
from src.filters import IsAdmin, IsBanned
from src.user_handlers import user_router, UserRegistration, show_confirmation_message
from src.admin_handlers import admin_router as admin_commands_router
from src.database import init_db, get_application_by_user_id
from src.keyboards import user_get_start_keyboard
from src.ban_manager import BanManager

# Настраиваем логгер для этого модуля
logger = logging.getLogger(__name__)

# --- ОСНОВНОЙ РОУТЕР ДЛЯ ОБЩИХ КОМАНД ---
common_router = Router(name="common_commands")

@common_router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext, bot: Bot):
    """
    Обрабатывает команду /start. Приветствует пользователя, проверяет наличие
    существующей заявки и предлагает дальнейшие действия с помощью клавиатуры.
    """
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} ({message.from_user.full_name}) запустил команду /start.")
    await state.clear()

    existing_application = await get_application_by_user_id(user_id)
    logger.info(f"Проверка существующей заявки для {user_id}: {'Найдена' if existing_application else 'Не найдена'}.")

    try:
        with open(GREETING_PICTURE_PATH, 'rb') as photo_file:
            photo = types.BufferedInputFile(photo_file.read(), filename='greeting.jpg')
    except Exception as e:
        logger.error(f"Не удалось открыть приветственное изображение по пути {GREETING_PICTURE_PATH}: {e}")
        photo = None

    greeting_text = f"👋 Привет, {message.from_user.full_name}!\n"
    greeting_text += "У вас уже есть сохраненная заявка.\n" if existing_application else "Готовы оставить заявку?\n"
    greeting_text += "(Кнопка ниже нажимается)"

    start_kb = user_get_start_keyboard(has_existing_application=bool(existing_application))

    if photo:
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=photo,
            caption=greeting_text,
            reply_markup=start_kb
        )
    else:
        await message.answer(greeting_text, reply_markup=start_kb)


@common_router.callback_query(F.data == "start_new_application")
async def cq_start_new_application(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие на кнопку 'Подать заявку' / 'Подать новую'.
    Начинает процесс сбора данных для новой заявки.
    """
    user_id = callback_query.from_user.id
    logger.info(f"Пользователь {user_id} инициировал создание новой заявки.")
    await state.clear()
    
    existing_application = await get_application_by_user_id(user_id)
    if existing_application:
        # Сохраняем ID существующей заявки для последующего обновления
        await state.update_data(existing_app_id=existing_application[0])
        logger.info(f"Для пользователя {user_id} найдена существующая заявка ID {existing_application[0]}, которая будет обновлена.")

    try:
        await callback_query.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение {callback_query.message.message_id} для пользователя {user_id}: {e}")

    await callback_query.message.answer("Отлично! Давайте начнем.\nДля начала, пожалуйста, напишите свой возраст (только цифры).")
    await state.set_state(UserRegistration.awaiting_age)
    await callback_query.answer()


@common_router.callback_query(F.data == "start_edit_application")
async def cq_start_edit_application(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие на кнопку 'Редактировать мою заявку'.
    Загружает существующие данные в FSM и переводит в режим подтверждения.
    """
    user_id = callback_query.from_user.id
    logger.info(f"Пользователь {user_id} инициировал редактирование существующей заявки.")
    await state.clear()

    existing_application = await get_application_by_user_id(user_id)

    if existing_application:
        app_id, _, username, full_name, age, citizenship, region_name, address, phone, status = existing_application
        
        await state.update_data(
            existing_app_id=app_id, age=age, citizenship=citizenship, region_name=region_name,
            address=address, phone=phone, db_username=username, db_full_name=full_name
        )
        logger.info(f"Данные заявки ID {app_id} для пользователя {user_id} загружены в FSM для редактирования.")
        
        try:
            await callback_query.message.delete()
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение {callback_query.message.message_id} при редактировании заявки: {e}")

        await state.set_state(UserRegistration.awaiting_confirmation)
        await show_confirmation_message(callback_query.message, state, edit_message=False)
    else:
        logger.warning(f"Пользователь {user_id} попытался редактировать заявку, но она не была найдена в БД.")
        await callback_query.message.edit_text("Ошибка: ваша заявка не найдена. Пожалуйста, подайте новую.")
    
    await callback_query.answer()


@common_router.message(Command("cancel"))
@common_router.message(F.text.casefold() == "отмена")
async def cmd_cancel(message: types.Message, state: FSMContext):
    """
    Обрабатывает команду /cancel или текст 'отмена'.
    Прерывает текущее действие (FSM) и сбрасывает состояние.
    """
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нечего отменять.", reply_markup=ReplyKeyboardRemove())
        return

    logger.info(f"Пользователь {message.from_user.id} отменил действие в состоянии {current_state}.")
    await state.clear()
    await message.answer("Действие отменено. Чтобы начать заново, введите /start", reply_markup=ReplyKeyboardRemove())


async def main():
    """Основная функция для настройки и запуска бота."""
    setup_logger()

    logger.info("Инициализация базы данных...")
    await init_db()
    
    logger.info("Проверка конфигурации...")
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN":
        logger.critical("Необходимо указать BOT_TOKEN в config.py!")
        return
    if not ADMIN_CHAT_ID_STR or ADMIN_CHAT_ID_STR == "YOUR_ADMIN_CHAT_ID_FOR_NOTIFICATIONS":
        logger.critical("Необходимо указать ADMIN_CHAT_ID_STR в config.py!")
        return
    
    try:
        admin_chat_id_for_notifications = int(ADMIN_CHAT_ID_STR)
    except ValueError:
        logger.critical(f"ADMIN_CHAT_ID_STR '{ADMIN_CHAT_ID_STR}' должен быть числом.")
        return

    admin_user_ids_list = []
    if ADMIN_USER_IDS_STR and ADMIN_USER_IDS_STR != "YOUR_USER_ID_1,YOUR_USER_ID_2":
        try:
            admin_user_ids_list = [int(uid.strip()) for uid in ADMIN_USER_IDS_STR.split(',') if uid.strip()]
            logger.info(f"Загружены ID администраторов: {admin_user_ids_list}")
        except ValueError:
            logger.error("Ошибка в ADMIN_USER_IDS_STR: должны быть только числа через запятую.")
    
    if not admin_user_ids_list:
        logger.warning("Список ADMIN_USER_IDS_STR пуст. Админ-команды будут недоступны.")

    logger.info("Настройка менеджера банов...")
    ban_manager_instance = BanManager()
    await ban_manager_instance.load_banned_users_from_db()
    for admin_id in admin_user_ids_list:
        # Это предотвращает админов от случайного использования пользовательских FSM
        await ban_manager_instance.add_banned_user(admin_id, 'admin_privilege')
    logger.info("Менеджер банов успешно загрузил данные из БД и кэшировал ID админов.")
    
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    try:
        await bot.set_my_commands(DEFAULT_BOT_COMMANDS, scope=BotCommandScopeAllPrivateChats())
        logger.info("Команды бота успешно установлены.")
    except Exception as e:
        logger.error(f"Не удалось установить команды бота: {e}")

    logger.info("Регистрация middlewares...")
    notification_mw = AdminChatIdMiddleware(admin_chat_id=admin_chat_id_for_notifications)
    dp.update.outer_middleware(BanManagerMiddleware(ban_manager=ban_manager_instance))
    user_router.callback_query.middleware(notification_mw)
    admin_commands_router.message.middleware(notification_mw)

    logger.info("Регистрация фильтров...")
    is_admin_filter = IsAdmin(admin_ids=admin_user_ids_list)
    is_banned_filter = IsBanned()
    private_chat_filter = F.chat.type == ChatType.PRIVATE
    private_callback_filter = F.message.chat.type == ChatType.PRIVATE

    # Применение фильтров к роутерам
    for router in [common_router, user_router, admin_commands_router]:
        router.message.filter(private_chat_filter)
        router.callback_query.filter(private_callback_filter)
    
    for router in [common_router, user_router]:
        router.message.filter(is_banned_filter)
        router.callback_query.filter(is_banned_filter)

    admin_commands_router.message.filter(is_admin_filter)
    admin_commands_router.callback_query.filter(is_admin_filter)
    logger.info("Все фильтры успешно применены к роутерам.")
    
    logger.info("Регистрация роутеров...")
    dp.include_routers(common_router, user_router, admin_commands_router)

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Бот запускается в режиме polling...")
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен вручную.")
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}", exc_info=True)