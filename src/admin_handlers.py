import logging
from datetime import datetime
from aiogram import Bot, Router, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.config import APPLICATIONS_PER_PAGE
from src.database import get_applications_paginated, get_application_by_id, update_application_status
from src.keyboards import get_admin_pagination_keyboard, get_admin_review_keyboard
from src.ban_manager import BanManager

logger = logging.getLogger(__name__)

class AdminActions(StatesGroup):
    """Определяет FSM состояния для действий администратора."""
    awaiting_message_to_user = State()
    reviewing_application = State()
    awaiting_rejection_reason = State()

admin_router = Router(name="admin_commands")


async def send_application_to_admins(
    bot: Bot, admin_chat_id: int, user_data: dict, from_user: types.User, app_id: int | None, is_update: bool = False
):
    """
    Формирует и отправляет уведомление о новой или обновленной заявке в чат администраторов.

    Args:
        bot: Экземпляр бота.
        admin_chat_id: ID чата для отправки уведомлений.
        user_data: Словарь с данными из заявки.
        from_user: Объект пользователя, отправившего заявку.
        app_id: ID заявки в базе данных.
        is_update: Флаг, указывающий на обновление существующей заявки.
    """
    status_text = "🔔 <b>Обновление заявки!</b>" if is_update or app_id else "🔔 <b>Новая заявка!</b>"
    if app_id:
        status_text += f" (ID: {app_id})"

    admin_message_text = (
        f"<b>От пользователя:</b> {from_user.full_name}\n"
        f"<b>ID:</b> {from_user.id}\n"
        f"<b>Username:</b> @{from_user.username or 'N/A'}\n\n"
        f"<b><u>Данные заявки:</u></b>\n"
        f"<b>Возраст:</b> {user_data.get('age', 'Не указан')}\n"
        f"<b>Гражданство:</b> {user_data.get('citizenship', 'Не указано')}\n"
        f"<b>Область:</b> {user_data.get('region_name', 'Не указано')}\n"
        f"<b>Адрес объекта:</b> {user_data.get('address', 'Не указано')}\n"
        f"<b>Телефон:</b> {user_data.get('phone', 'Не указан')}"
    )
    
    full_admin_message = f"{status_text}\n\n{admin_message_text}"

    try:
        await bot.send_message(chat_id=admin_chat_id, text=full_admin_message, parse_mode=ParseMode.HTML)
        logger.info(f"Уведомление о заявке ID {app_id or 'новая'} от {from_user.id} успешно отправлено в чат {admin_chat_id}.")
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление о заявке в чат {admin_chat_id}: {e}", exc_info=True)


async def show_applications_page(target: types.Message | types.CallbackQuery, page: int = 1, is_edit: bool = False):
    """
    Отображает страницу со списком заявок для администратора.

    Args:
        target: Объект Message или CallbackQuery, на который нужно ответить.
        page: Номер страницы для отображения.
        is_edit: Флаг, указывающий на необходимость редактирования существующего сообщения.
    """
    logger.info(f"Запрос на отображение страницы {page} заявок. Редактирование: {is_edit}.")
    apps_on_page, total_pages, total_items = await get_applications_paginated(
        page=page, 
        per_page=APPLICATIONS_PER_PAGE,
        status_filter=['new', 'updated', 'updated_conflict']
    )

    if not apps_on_page:
        text = "Нет доступных заявок для просмотра."
        final_reply_markup = None
        logger.info("Нет активных заявок для отображения администратору.")
    else:
        text_parts = [f"📝 <b>Заявки (Страница {page}/{total_pages}, Всего: {total_items}):</b>\n"]
        all_keyboard_rows = [] 

        for app_data in apps_on_page:
            (app_id, user_id, username, full_name, _, _, _, _, phone, status, created_at, updated_at) = app_data[:12]
            date_to_show_str = updated_at if status != 'new' else created_at
            formatted_date = datetime.strptime(date_to_show_str, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%y %H:%M')

            text_parts.append(
                f"\n<b>Заявка #{app_id}</b> (Статус: <code>{status}</code>)\n"
                f"От: {formatted_date}\n"
                f"Пользователь: {full_name} (@{username or 'N/A'}, ID: {user_id})\n"
                f"Телефон: {phone}\n"
            )
            all_keyboard_rows.append([InlineKeyboardButton(text=f"Рассмотреть заявку #{app_id}", callback_data=f"admin_app_review_{app_id}_{page}")])

        text = "".join(text_parts)
        pagination_kb = get_admin_pagination_keyboard(page, total_pages, action_prefix="admin_viewapps_page_")
        if pagination_kb:
            all_keyboard_rows.extend(pagination_kb.inline_keyboard)
        
        final_reply_markup = InlineKeyboardMarkup(inline_keyboard=all_keyboard_rows)
    
    # Отправка или редактирование сообщения
    target_message = target.message if isinstance(target, types.CallbackQuery) else target
    try:
        if is_edit:
            await target_message.edit_text(text, reply_markup=final_reply_markup, parse_mode=ParseMode.HTML)
        else:
            await target_message.answer(text, reply_markup=final_reply_markup, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Не удалось отправить/отредактировать сообщение со списком заявок: {e}. Отправка нового сообщения.")
        # Если редактирование не удалось (например, текст не изменился), отправляем новое сообщение
        await target_message.answer(text, reply_markup=final_reply_markup, parse_mode=ParseMode.HTML)

    if isinstance(target, types.CallbackQuery):
        await target.answer()


@admin_router.message(Command("view_apps"))
async def cmd_view_applications(message: types.Message, state: FSMContext):
    """Обрабатывает команду /view_apps, отображая первую страницу заявок."""
    logger.info(f"Администратор {message.from_user.id} вызвал команду /view_apps.")
    await state.clear()
    await show_applications_page(message, page=1, is_edit=False)


@admin_router.callback_query(F.data.startswith("admin_viewapps_page_"))
async def cq_admin_view_applications_page(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает пагинацию в списке заявок."""
    page = int(callback_query.data.split("_")[-1])
    logger.info(f"Администратор {callback_query.from_user.id} переключил страницу заявок на {page}.")
    await state.clear()
    await show_applications_page(callback_query, page=page, is_edit=True)


@admin_router.callback_query(F.data.startswith("admin_app_review_"))
async def cq_admin_app_start_review(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие 'Рассмотреть заявку', отображая детальную информацию и кнопки действий.
    """
    parts = callback_query.data.split("_")
    app_id = int(parts[-2])
    current_page = int(parts[-1])
    admin_id = callback_query.from_user.id
    
    logger.info(f"Администратор {admin_id} начал просмотр заявки #{app_id} со страницы {current_page}.")
    app_data = await get_application_by_id(app_id)
    if not app_data:
        logger.warning(f"Администратор {admin_id} попытался просмотреть несуществующую заявку #{app_id}.")
        await callback_query.answer(f"Заявка #{app_id} не найдена или уже обработана.", show_alert=True)
        await show_applications_page(callback_query, page=current_page, is_edit=True) # Обновляем список
        return

    (id_db, user_id, username, full_name, age, citizenship, region, address, phone, status, created_at, updated_at) = app_data
    
    await state.set_state(AdminActions.reviewing_application)
    await state.update_data(
        current_app_id=id_db, current_app_user_id=user_id, current_app_user_name=full_name,
        current_app_page_from_list=current_page, current_app_status=status
    )
    logger.debug(f"Состояние FSM обновлено для просмотра заявки #{app_id}. Данные: {await state.get_data()}")

    created_at_str = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y %H:%M')
    updated_at_str = datetime.strptime(updated_at, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y %H:%M')
    
    review_text = (
        f"📝 <b>Просмотр заявки #{id_db}</b> (Статус: <code>{status}</code>)\n"
        f"Создана: {created_at_str}, Обновлена: {updated_at_str}\n\n"
        f"<b>Пользователь:</b> {full_name} (@{username or 'N/A'}, ID: {user_id})\n"
        f"<b>Возраст:</b> {age}\n"
        f"<b>Гражданство:</b> {citizenship}\n"
        f"<b>Область:</b> {region}\n"
        f"<b>Адрес:</b> {address}\n"
        f"<b>Телефон:</b> {phone}\n\n"
        f"Выберите действие:"
    )
    review_keyboard = get_admin_review_keyboard(id_db, current_page, user_id)
    
    await callback_query.message.edit_text(review_text, reply_markup=review_keyboard, parse_mode=ParseMode.HTML)
    await callback_query.answer()


@admin_router.callback_query(AdminActions.reviewing_application, F.data.startswith("admin_review_write_"))
async def cq_admin_review_write_start(callback_query: types.CallbackQuery, state: FSMContext):
    """Переводит администратора в состояние ожидания текста для отправки пользователю."""
    admin_state_data = await state.get_data()
    user_full_name = admin_state_data.get("current_app_user_name")
    app_id = admin_state_data.get("current_app_id")

    logger.info(f"Администратор {callback_query.from_user.id} начал писать сообщение по заявке #{app_id}.")
    await state.set_state(AdminActions.awaiting_message_to_user)
    
    await callback_query.message.edit_text(
        f"✏️ Введите сообщение для пользователя {user_full_name} (заявка #{app_id}).\nДля отмены введите /cancel",
        reply_markup=None
    )
    await callback_query.answer()


@admin_router.callback_query(AdminActions.reviewing_application, F.data.startswith("admin_review_complete_"))
async def cq_admin_review_complete(callback_query: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Обрабатывает утверждение заявки."""
    admin_state_data = await state.get_data()
    app_id = admin_state_data.get("current_app_id")
    user_id_to_notify = admin_state_data.get("current_app_user_id")
    page_to_return = admin_state_data.get("current_app_page_from_list", 1)
    admin_id = callback_query.from_user.id

    if not app_id:
        logger.error(f"Критическая ошибка FSM: не найден app_id в состоянии для администратора {admin_id}.")
        await callback_query.answer("Ошибка: ID заявки не найден.", show_alert=True)
        return

    logger.info(f"Администратор {admin_id} утвердил заявку #{app_id}.")
    await update_application_status(app_id, "completed", admin_id=admin_id)
    
    try:
        await bot.send_message(user_id_to_notify, f"🎉 Ваша заявка #{app_id} была принята! Скоро с Вами свяжутся.")
        logger.info(f"Пользователю {user_id_to_notify} отправлено уведомление о принятии заявки #{app_id}.")
    except Exception as e:
        logger.warning(f"Не удалось уведомить пользователя {user_id_to_notify} о принятии заявки #{app_id}: {e}")

    await callback_query.answer(f"Заявка #{app_id} отмечена как 'завершенная'.", show_alert=True)
    await state.clear()
    await show_applications_page(callback_query, page=page_to_return, is_edit=True)


@admin_router.callback_query(AdminActions.reviewing_application, F.data.startswith("admin_review_reject_"))
async def cq_admin_review_reject_start(callback_query: types.CallbackQuery, state: FSMContext):
    """Переводит администратора в состояние ожидания причины отклонения заявки."""
    app_id = (await state.get_data()).get("current_app_id")
    logger.info(f"Администратор {callback_query.from_user.id} начал отклонение заявки #{app_id}.")
    await state.set_state(AdminActions.awaiting_rejection_reason)
    
    await callback_query.message.edit_text(
        f"📝 Введите причину отклонения заявки #{app_id}:\nЧтобы отменить, введите /cancel",
        reply_markup=None
    )
    await callback_query.answer()


@admin_router.message(AdminActions.awaiting_rejection_reason, F.text)
async def process_rejection_reason(message: types.Message, state: FSMContext, bot: Bot):
    """Обрабатывает введенную причину отклонения, обновляет статус и уведомляет пользователя."""
    rejection_reason = message.text
    admin_data = await state.get_data()
    app_id = admin_data.get("current_app_id")
    user_id_to_notify = admin_data.get("current_app_user_id")
    page_to_return = admin_data.get("current_app_page_from_list", 1)
    admin_id = message.from_user.id

    if not all([app_id, user_id_to_notify]):
        logger.error(f"Критическая ошибка FSM: не найдены данные для отклонения заявки для админа {admin_id}.")
        await message.answer("Произошла ошибка. Попробуйте снова.")
        await state.clear()
        return

    logger.info(f"Администратор {admin_id} отклонил заявку #{app_id}. Причина: {rejection_reason}")
    await update_application_status(app_id, 'rejected', admin_id=admin_id)
    
    try:
        await bot.send_message(user_id_to_notify, f"ℹ️ К сожалению, ваша заявка #{app_id} была отклонена.\nПричина: {rejection_reason}\nОбновите заявку и попробуйте отправить её снова.")
        logger.info(f"Пользователю {user_id_to_notify} отправлено уведомление об отклонении заявки.")
    except Exception as e:
        logger.warning(f"Не удалось уведомить пользователя {user_id_to_notify} об отклонении: {e}")
    
    await message.answer(f"✅ Заявка #{app_id} отклонена. Пользователь уведомлен.")
    await state.clear()
    await show_applications_page(message, page=page_to_return, is_edit=False)


@admin_router.callback_query(AdminActions.reviewing_application, F.data.startswith("admin_review_backtolist_"))
async def cq_admin_review_backtolist(callback_query: types.CallbackQuery, state: FSMContext):
    """Возвращает администратора из детального просмотра обратно к списку заявок."""
    page_to_return = int(callback_query.data.split("_")[-1])
    logger.info(f"Администратор {callback_query.from_user.id} вернулся к списку заявок на страницу {page_to_return}.")
    await state.clear()
    await show_applications_page(callback_query, page=page_to_return, is_edit=True)


@admin_router.callback_query(AdminActions.reviewing_application, F.data.startswith("admin_ban_user_"))
async def cq_admin_ban_user(callback_query: types.CallbackQuery, bot: Bot, state: FSMContext, ban_manager: BanManager):
    """Блокирует пользователя, связанного с заявкой."""
    parts = callback_query.data.split("_")
    user_to_ban_id = int(parts[-1])
    app_id = int(parts[-2])
    page_to_return = int(parts[-3])
    admin_id = callback_query.from_user.id

    logger.info(f"Администратор {admin_id} инициировал бан пользователя {user_to_ban_id} из заявки #{app_id}.")
    await ban_manager.add_banned_user(user_to_ban_id, f'banned by admin {admin_id}')
    
    try:
        await bot.send_message(user_to_ban_id, "⛔️ Вы были заблокированы администратором.")
        logger.info(f"Пользователю {user_to_ban_id} отправлено уведомление о блокировке.")
    except Exception as e:
        logger.warning(f"Не удалось уведомить пользователя {user_to_ban_id} о блокировке: {e}")
    
    await callback_query.answer(f"Пользователь {user_to_ban_id} заблокирован.", show_alert=True)
    await state.clear()
    await show_applications_page(callback_query, page=page_to_return, is_edit=True)


@admin_router.message(AdminActions.awaiting_message_to_user, F.text)
async def process_admin_message_to_user(message: types.Message, state: FSMContext, bot: Bot):
    """Обрабатывает введенный админом текст и отправляет его пользователю."""
    admin_message_text = message.text
    admin_data = await state.get_data()
    target_user_id = admin_data.get("current_app_user_id")
    target_app_id = admin_data.get("current_app_id")
    admin_id = message.from_user.id
    page_to_return = admin_data.get("current_app_page_from_list", 1)

    if not all([target_user_id, target_app_id]):
        logger.error(f"Критическая ошибка FSM: не найдены данные для отправки сообщения от админа {admin_id}.")
        await message.answer("Произошла ошибка. Попробуйте снова.")
        await state.clear()
        return

    logger.info(f"Администратор {admin_id} отправляет сообщение пользователю {target_user_id} по заявке #{target_app_id}.")
    try:
        await bot.send_message(target_user_id, f"Сообщение от администратора по вашей заявке #{target_app_id}:\n\n{admin_message_text}")
        await message.answer("✅ Сообщение успешно отправлено пользователю.")
        logger.info(f"Сообщение пользователю {target_user_id} успешно отправлено.")
    except Exception as e:
        await message.answer(f"⚠️ Не удалось отправить сообщение: {e}")
        logger.error(f"Ошибка при отправке сообщения от {admin_id} к {target_user_id}: {e}", exc_info=True)

    # После отправки возвращаемся в режим детального просмотра
    await show_applications_page(message, page=page_to_return, is_edit=True)


@admin_router.message(Command("cancel_admin_action"), AdminActions.awaiting_message_to_user)
async def cmd_cancel_admin_action(message: types.Message, state: FSMContext):
    """Отменяет текущее FSM-действие администратора (напр., ввод причины отклонения)."""
    current_state = await state.get_state()
    logger.info(f"Администратор {message.from_user.id} отменил действие в состоянии {current_state}.")
    
    admin_data = await state.get_data()
    page_to_return = admin_data.get("current_app_page_from_list", 1)
    
    await state.clear()
    await message.answer("Действие отменено. Возврат к списку заявок.")
    await show_applications_page(message, page=page_to_return, is_edit=False)


@admin_router.callback_query(F.data == "admin_noop")
async def cq_admin_noop(callback_query: types.CallbackQuery):
    """Пустой обработчик для кнопок, не требующих действий (например, заголовок)."""
    await callback_query.answer()

__all__ = ['admin_router', 'send_application_to_admins', 'AdminActions']