from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

USER_ASK_REGION = [
    [InlineKeyboardButton(text="Московская область", callback_data="region_msk")],
    [InlineKeyboardButton(text="Владимирская область", callback_data="region_vldmr")],
]

USER_ASK_ADDRESS_MSK = [
    [InlineKeyboardButton(text="посёлок совхоза Останино, Дорожная, 28А", callback_data="address_msk_1")],
    [InlineKeyboardButton(text="г. Королев Лесная, 6", callback_data="address_msk_2")],
    [InlineKeyboardButton(text="д. Большие Жеребцы Восточная, 1к8", callback_data="address_msk_3")],
    [InlineKeyboardButton(text="пос. Софрино Тютчева, с15", callback_data="address_msk_4")],
    [InlineKeyboardButton(text="г. Мытищи Калинина, 6", callback_data="address_msk_5")],
    [InlineKeyboardButton(text="с. Васильевское 22А", callback_data="address_msk_6")],
    [InlineKeyboardButton(text="посёлок санатория Тишково, Курортная улица, 2", callback_data="address_msk_7")],
    [InlineKeyboardButton(text="Сергиев Посад, Пограничная улица 32", callback_data="address_msk_8")],
    [InlineKeyboardButton(text="Пушкино, Железнодорожная улица, 6", callback_data="address_msk_9")],
    [InlineKeyboardButton(text="Мытищи, Калинина, 6", callback_data="address_msk_10")],
    [InlineKeyboardButton(text="посёлок Софрино, Тютчева с15", callback_data="address_msk_11")],
]

USER_ASK_ADDRESS_VLDMR = [
    [InlineKeyboardButton(text="г. Кольчугино, улица Максимова, 11", callback_data="address_vldmr_1")],
    [InlineKeyboardButton(text="г. Петушки Московская, 16", callback_data="address_vldmr_2")],
    [InlineKeyboardButton(text="г. Александров Королёва, 4к2", callback_data="address_vldmr_3")],
    [InlineKeyboardButton(text="г. Александров Королёва, 9", callback_data="address_vldmr_4")],
    [InlineKeyboardButton(text="г. Александров Гагарина, 23к1", callback_data="address_vldmr_5")],
    [InlineKeyboardButton(text="Струнино Заречная, 32", callback_data="address_vldmr_6")],
    [InlineKeyboardButton(text="Александров, улица Жулёва, 3", callback_data="address_vldmr_7")],
    [InlineKeyboardButton(text="г. Александров Кольчугинская 49с1", callback_data="address_vldmr_8")],
    [InlineKeyboardButton(text="Александров, Улица Геологов, 8", callback_data="address_vldmr_9")],
    [InlineKeyboardButton(text="г. Кольчугино, улица Железнодорожная, 31", callback_data="address_vldmr_10")],
    [InlineKeyboardButton(text="посёлок Городищи, Советская, 18", callback_data="address_vldmr_11")],
]

USER_ASK_CONFIRMATION = [
    [InlineKeyboardButton(text="Редактировать возраст", callback_data="edit_age")],
    [InlineKeyboardButton(text="Редактировать гражданство", callback_data="edit_citizenship")],
    [InlineKeyboardButton(text="Редактировать регион", callback_data="edit_region")],
    [InlineKeyboardButton(text="Редактировать адрес", callback_data="edit_address")],
    [InlineKeyboardButton(text="Редактировать телефон", callback_data="edit_phone")],
    [InlineKeyboardButton(text="✅ Все верно, отправить", callback_data="confirm_submission")],
    [InlineKeyboardButton(text="❌ Отменить и начать заново", callback_data="cancel_submission")],
]

def user_get_start_keyboard(has_existing_application: bool) -> InlineKeyboardMarkup:
    buttons = []
    if has_existing_application:
        buttons.append([InlineKeyboardButton(text="✏️ Редактировать мою заявку", callback_data="start_edit_application")])
        buttons.append([InlineKeyboardButton(text="📝 Подать новую (заменит старую)", callback_data="start_new_application")])
    else:
        buttons.append([InlineKeyboardButton(text="📝 Подать заявку", callback_data="start_new_application")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_region_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=USER_ASK_REGION)

def get_address_keyboard(region_code: str) -> InlineKeyboardMarkup | None:
    now_keyboard = None
    if region_code == 'msk':
        now_keyboard = InlineKeyboardMarkup(inline_keyboard=USER_ASK_ADDRESS_MSK)
    elif region_code == 'vldmr':
        now_keyboard = InlineKeyboardMarkup(inline_keyboard=USER_ASK_ADDRESS_VLDMR)
    return now_keyboard

async def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=USER_ASK_CONFIRMATION)

def get_admin_pagination_keyboard(current_page: int, total_pages: int, action_prefix: str = "admin_apps_page_") -> InlineKeyboardMarkup | None:
    """
    Клавиатура для пагинации списка заявок.
    action_prefix позволяет использовать эту клавиатуру для разных списков (например, новые, в работе и т.д.)
    """
    if total_pages <= 1:
        return None

    buttons_row = []
    if current_page > 1:
        buttons_row.append(InlineKeyboardButton(text="⬅️ Пред.", callback_data=f"{action_prefix}{current_page - 1}"))
    
    buttons_row.append(InlineKeyboardButton(text=f"📄 {current_page}/{total_pages}", callback_data="admin_noop")) # noop - нет операции

    if current_page < total_pages:
        buttons_row.append(InlineKeyboardButton(text="След. ➡️", callback_data=f"{action_prefix}{current_page + 1}"))
    
    return InlineKeyboardMarkup(inline_keyboard=[buttons_row])

def get_admin_review_keyboard(app_id: int, current_page: int) -> InlineKeyboardMarkup:
    """
    Клавиатура для детального просмотра и действий с одной заявкой.
    current_page - страница списка, на которую нужно вернуться.
    """
    buttons = [
        [InlineKeyboardButton(text="✉️ Написать пользователю", callback_data=f"admin_review_write_{app_id}_{current_page}")],
        [InlineKeyboardButton(text="🏁 Завершить заявку", callback_data=f"admin_review_complete_{app_id}_{current_page}")],
        [InlineKeyboardButton(text="❌ Отклонить заявку", callback_data=f"admin_review_reject_{app_id}_{current_page}")],
        [InlineKeyboardButton(text="⛔ Заблокировать пользователя", callback_data=f"admin_ban_user_{app_id}_{current_page}")],
        [InlineKeyboardButton(text="⬅️ К списку заявок", callback_data=f"admin_review_backtolist_{current_page}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)