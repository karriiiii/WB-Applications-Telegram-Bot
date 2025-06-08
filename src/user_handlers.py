import logging
import re
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ParseMode

from src.admin_handlers import send_application_to_admins
from src.keyboards import (
    USER_ASK_REGION, USER_ASK_ADDRESS_MSK, USER_ASK_ADDRESS_VLDMR,
    get_address_keyboard, get_region_keyboard, get_confirmation_keyboard
)
from src.database import add_or_update_application

# Настраиваем логгер для этого модуля
logger = logging.getLogger(__name__)

user_router = Router(name="user_registration")

class UserRegistration(StatesGroup):
    """Состояния для конечного автомата регистрации пользователя."""
    awaiting_age = State()
    awaiting_citizenship = State()
    awaiting_region = State()
    awaiting_address = State()
    awaiting_phone = State()
    awaiting_confirmation = State()

async def show_confirmation_message(message_or_cq: Message | CallbackQuery, state: FSMContext, edit_message: bool = False):
    """
    Формирует и отправляет/редактирует сообщение с итоговыми данными для подтверждения.

    Args:
        message_or_cq: Объект Message или CallbackQuery, на который нужно ответить.
        state: Контекст FSM для получения данных пользователя.
        edit_message: Флаг, указывающий, нужно ли редактировать существующее сообщение.
    """
    user_data = await state.get_data()
    user_id = message_or_cq.from_user.id
    logger.info(f"Показ страницы подтверждения для пользователя {user_id}. Данные: {user_data}")
    
    text = (
        f"📝 <b>Пожалуйста, проверьте введенные данные:</b>\n\n"
        f"<b>Возраст:</b> {user_data.get('age', 'Не указан')}\n"
        f"<b>Гражданство:</b> {user_data.get('citizenship', 'Не указано')}\n"
        f"<b>Область:</b> {user_data.get('region_name', 'Не указана')}\n"
        f"<b>Адрес объекта:</b> {user_data.get('address', 'Не указан')}\n"
        f"<b>Телефон:</b> {user_data.get('phone', 'Не указан')}\n\n"
        f"<b>Все верно?</b>"
    )
    keyboard = await get_confirmation_keyboard()
    
    # Редактируем сообщение, если это callback или указан флаг
    if isinstance(message_or_cq, CallbackQuery) or edit_message:
        await message_or_cq.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    else: # Отправляем новое сообщение
        await message_or_cq.answer(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)

    if isinstance(message_or_cq, CallbackQuery):
        await message_or_cq.answer()

# --- Обработчики FSM ---

@user_router.message(UserRegistration.awaiting_age)
async def process_age(message: Message, state: FSMContext):
    """Обрабатывает введенный возраст, валидирует и переходит к следующему шагу."""
    user_id = message.from_user.id
    if not message.text or not message.text.isdigit():
        logger.warning(f"Пользователь {user_id} ввел некорректный возраст (не цифры): '{message.text}'")
        await message.answer("Пожалуйста, введите возраст цифрами. Например: 25")
        return
    
    age = int(message.text)
    if not (5 < age < 100):
        logger.warning(f"Пользователь {user_id} ввел некорректный возраст (вне диапазона): {age}")
        await message.answer("Пожалуйста, укажите корректный возраст (от 6 до 99 лет).")
        return
    
    await state.update_data(age=age)
    user_data = await state.get_data()
    
    if user_data.get("editing_now"):
        logger.info(f"Пользователь {user_id} завершил редактирование возраста. Возврат к подтверждению.")
        await state.update_data(editing_now=False)
        await state.set_state(UserRegistration.awaiting_confirmation)
        await show_confirmation_message(message, state)
    else:
        logger.info(f"Пользователь {user_id} указал возраст: {age}. Переход к шагу 'гражданство'.")
        await message.answer("Отлично! Теперь укажите свое гражданство.")
        await state.set_state(UserRegistration.awaiting_citizenship)

@user_router.message(UserRegistration.awaiting_citizenship)
async def process_citizenship(message: Message, state: FSMContext):
    """Обрабатывает введенное гражданство и переходит к следующему шагу."""
    user_id = message.from_user.id
    citizenship = message.text.strip()
    if not citizenship or len(citizenship) < 2:
        logger.warning(f"Пользователь {user_id} ввел некорректное гражданство: '{citizenship}'")
        await message.answer("Пожалуйста, введите корректное название страны/гражданства.")
        return

    await state.update_data(citizenship=citizenship)
    user_data = await state.get_data()

    if user_data.get("editing_now"):
        logger.info(f"Пользователь {user_id} завершил редактирование гражданства. Возврат к подтверждению.")
        await state.update_data(editing_now=False)
        await state.set_state(UserRegistration.awaiting_confirmation)
        await show_confirmation_message(message, state)
    else:
        logger.info(f"Пользователь {user_id} указал гражданство: '{citizenship}'. Переход к выбору региона.")
        await message.answer(
            "Хорошо. В какой области Вы ищете работу?",
            reply_markup=get_region_keyboard()
        )
        await state.set_state(UserRegistration.awaiting_region)

@user_router.callback_query(UserRegistration.awaiting_region, F.data.startswith("region_"))
async def process_region_callback(callback_query: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор региона через кнопку и предлагает выбрать адрес."""
    region_code = callback_query.data.split("_")[1]
    
    # Находим текст кнопки по callback_data
    selected_region_text = next(
        (btn.text for row in USER_ASK_REGION for btn in row if btn.callback_data == callback_query.data),
        "Не указан"
    )
            
    await state.update_data(region_code=region_code, region_name=selected_region_text)
    logger.info(f"Пользователь {callback_query.from_user.id} выбрал регион: {selected_region_text} ({region_code}).")

    address_keyboard = get_address_keyboard(region_code)
    if address_keyboard:
        await callback_query.message.edit_text(
            f"Вы выбрали: {selected_region_text}.\nТеперь выберите адрес объекта:",
            reply_markup=address_keyboard
        )
        await state.set_state(UserRegistration.awaiting_address)
    else:
        logger.error(f"Не найдена клавиатура адресов для региона '{region_code}'.")
        await callback_query.message.edit_text("Ошибка: не найдена клавиатура адресов.")
        await callback_query.answer("Ошибка конфигурации", show_alert=True)
    await callback_query.answer()

@user_router.message(UserRegistration.awaiting_region)
async def process_region_text_instead_of_button(message: Message):
    """Ловит текстовый ввод вместо нажатия кнопки выбора региона."""
    logger.warning(f"Пользователь {message.from_user.id} ввел текст вместо выбора региона.")
    await message.answer(
        "Пожалуйста, выберите регион из предложенных вариантов, нажав на кнопку.",
        reply_markup=get_region_keyboard()
    )

@user_router.callback_query(UserRegistration.awaiting_address, F.data.startswith("address_"))
async def process_address_callback(callback_query: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор адреса через кнопку и переходит к вводу телефона."""
    user_data = await state.get_data()
    region_code = user_data.get('region_code')
    
    source_keyboard_data = USER_ASK_ADDRESS_MSK if region_code == 'msk' else USER_ASK_ADDRESS_VLDMR if region_code == 'vldmr' else None
    selected_address_text = "Не указан"
    if source_keyboard_data:
        selected_address_text = next(
            (btn.text for row in source_keyboard_data for btn in row if btn.callback_data == callback_query.data),
            "Не указан"
        )

    await state.update_data(address=selected_address_text)
    logger.info(f"Пользователь {callback_query.from_user.id} выбрал адрес: {selected_address_text}.")
    
    current_user_data = await state.get_data()
    if current_user_data.get("editing_now"):
        logger.info(f"Пользователь {callback_query.from_user.id} завершил редактирование адреса. Возврат к подтверждению.")
        await state.update_data(editing_now=False)
        await state.set_state(UserRegistration.awaiting_confirmation)
        await show_confirmation_message(callback_query, state, edit_message=True)
    else:
        await callback_query.message.edit_text(
            f"Вы выбрали адрес: {selected_address_text}.\n"
            "Теперь, пожалуйста, укажите ваш контактный номер телефона (например, +79001234567 или 89001234567)."
        )
        await state.set_state(UserRegistration.awaiting_phone)
    await callback_query.answer()

@user_router.message(UserRegistration.awaiting_address)
async def process_address_text_instead_of_button(message: Message, state: FSMContext):
    """Ловит текстовый ввод вместо нажатия кнопки выбора адреса."""
    logger.warning(f"Пользователь {message.from_user.id} ввел текст вместо выбора адреса.")
    user_data = await state.get_data()
    region_code = user_data.get('region_code')
    address_keyboard = get_address_keyboard(region_code)
    await message.answer(
        "Пожалуйста, выберите адрес из предложенных вариантов, нажав на кнопку.",
        reply_markup=address_keyboard
    )

@user_router.message(UserRegistration.awaiting_phone)
async def process_phone(message: Message, state: FSMContext):
    """Обрабатывает введенный телефон, валидирует и переходит к подтверждению."""
    user_id = message.from_user.id
    phone_number = message.text.strip()
    
    # Нормализуем номер для проверки
    normalized_phone = re.sub(r"[ \-\(\)]", "", phone_number)
    
    if not re.fullmatch(r"(\+7|8)\d{10}", normalized_phone):
        logger.warning(f"Пользователь {user_id} ввел некорректный телефон: '{phone_number}'")
        await message.answer(
            "Пожалуйста, введите корректный номер телефона в формате +7XXXXXXXXXX или 8XXXXXXXXXX."
        )
        return

    await state.update_data(phone=phone_number)
    logger.info(f"Пользователь {user_id} указал телефон. Переход к подтверждению анкеты.")
    
    await state.set_state(UserRegistration.awaiting_confirmation)
    await show_confirmation_message(message, state)

# --- Хендлеры для этапа подтверждения ---

@user_router.callback_query(UserRegistration.awaiting_confirmation, F.data.startswith("edit_"))
async def process_edit_action(callback_query: CallbackQuery, state: FSMContext):
    """Обрабатывает нажатие кнопок 'Изменить...' и переводит FSM в нужное состояние."""
    action = callback_query.data.split("_")[1]
    user_id = callback_query.from_user.id
    logger.info(f"Пользователь {user_id} начал редактирование поля '{action}'.")
    await state.update_data(editing_now=True)

    actions = {
        "age": ("Введите новый возраст:", UserRegistration.awaiting_age),
        "citizenship": ("Введите новое гражданство:", UserRegistration.awaiting_citizenship),
        "phone": ("Введите новый номер телефона:", UserRegistration.awaiting_phone),
    }

    if action in actions:
        text, new_state = actions[action]
        await callback_query.message.edit_text(text)
        await state.set_state(new_state)
    elif action == "region":
        await callback_query.message.edit_text("Выберите новый регион:", reply_markup=get_region_keyboard())
        await state.set_state(UserRegistration.awaiting_region)
    elif action == "address":
        user_data = await state.get_data()
        region_code = user_data.get("region_code")
        address_keyboard = get_address_keyboard(region_code)
        await callback_query.message.edit_text("Выберите новый адрес:", reply_markup=address_keyboard)
        await state.set_state(UserRegistration.awaiting_address)
    
    await callback_query.answer()

@user_router.callback_query(UserRegistration.awaiting_confirmation, F.data == "confirm_submission")
async def process_confirm_submission(callback_query: CallbackQuery, state: FSMContext, bot: Bot, admin_chat_id_from_mw: int):
    """Обрабатывает финальное подтверждение, сохраняет данные и отправляет уведомление."""
    user_id = callback_query.from_user.id
    logger.info(f"Пользователь {user_id} подтвердил свою заявку. Начинаем обработку.")
    
    user_data = await state.get_data()
    await state.clear()

    await callback_query.message.edit_text(
        "✅ Спасибо! Ваша заявка отправлена администраторам.",
        reply_markup=None
    )
    await callback_query.answer()

    try:
        await add_or_update_application(
            user_id=user_id,
            username=callback_query.from_user.username,
            full_name=callback_query.from_user.full_name,
            user_data=user_data,
            existing_app_id=user_data.get("existing_app_id")
        )
        await send_application_to_admins(
            bot=bot,
            admin_chat_id=admin_chat_id_from_mw,
            user_data=user_data,
            from_user=callback_query.from_user,
            app_id=user_data.get("existing_app_id")
        )
        logger.info(f"Заявка от пользователя {user_id} успешно сохранена в БД и отправлена администраторам.")
    except Exception as e:
        logger.error(f"Ошибка при отправке или сохранении заявки от пользователя {user_id}: {e}", exc_info=True)
        await callback_query.message.answer("Произошла ошибка при отправке вашей заявки. Пожалуйста, попробуйте позже.")

@user_router.callback_query(UserRegistration.awaiting_confirmation, F.data == "cancel_submission")
async def process_cancel_submission(callback_query: CallbackQuery, state: FSMContext):
    """Обрабатывает отмену подачи заявки."""
    user_id = callback_query.from_user.id
    logger.info(f"Пользователь {user_id} отменил подачу заявки.")
    await state.clear()
    await callback_query.message.edit_text(
        "Заявка отменена. Чтобы начать заново, введите /start",
        reply_markup=None
    )
    await callback_query.answer()

@user_router.message(UserRegistration.awaiting_confirmation)
async def process_text_in_confirmation(message: Message, state: FSMContext):
    """Ловит текстовые сообщения на этапе подтверждения."""
    logger.warning(f"Пользователь {message.from_user.id} ввел текст на этапе подтверждения.")
    await message.answer("Пожалуйста, используйте кнопки для подтверждения или редактирования данных.")
    await show_confirmation_message(message, state)


__all__ = ['user_router', 'UserRegistration', 'show_confirmation_message']