import logging
import aiosqlite
from math import ceil

from src.config import DATABASE_FILE

# Настраиваем логгер для этого модуля
logger = logging.getLogger(__name__)

async def init_db():
    """Инициализирует базу данных и создает таблицы, если они не существуют."""
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL UNIQUE,
                    username TEXT,
                    full_name TEXT,
                    age INTEGER,
                    citizenship TEXT,
                    region_name TEXT,
                    address TEXT,
                    phone TEXT,
                    status TEXT DEFAULT 'new',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)
            await db.execute("""
                CREATE TRIGGER IF NOT EXISTS update_applications_updated_at
                AFTER UPDATE ON applications
                FOR EACH ROW
                BEGIN
                    UPDATE applications SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
                END;
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS blocked_users (
                    user_id INTEGER NOT NULL UNIQUE,
                    reason TEXT
                );
            """)
            await db.commit()
        logger.info(f"База данных '{DATABASE_FILE}' успешно инициализирована/проверена.")
    except aiosqlite.Error as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}", exc_info=True)
        raise


async def get_application_by_user_id(user_id: int) -> tuple | None:
    """
    Получает заявку пользователя по его Telegram user_id.

    Args:
        user_id: Уникальный идентификатор пользователя в Telegram.

    Returns:
        Кортеж с данными заявки, если она найдена, иначе None.
    """
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            async with db.execute(
                "SELECT id, user_id, username, full_name, age, citizenship, region_name, address, phone, status FROM applications WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                application = await cursor.fetchone()
                if application:
                    logger.info(f"Найдена заявка (id: {application[0]}) для пользователя {user_id}.")
                else:
                    logger.info(f"Заявка для пользователя {user_id} не найдена в БД.")
                return application
    except aiosqlite.Error as e:
        logger.error(f"Ошибка при поиске заявки для user_id {user_id}: {e}", exc_info=True)
        return None


async def add_or_update_application(
    user_id: int,
    username: str | None,
    full_name: str,
    user_data: dict,
    existing_app_id: int | None = None
):
    """
    Добавляет новую заявку или обновляет существующую в базе данных.

    Args:
        user_id: Уникальный идентификатор пользователя в Telegram.
        username: Имя пользователя в Telegram.
        full_name: Полное имя пользователя.
        user_data: Словарь с дополнительными данными заявки (age, citizenship и т.д.).
        existing_app_id: ID существующей заявки для обновления. Если None, создается новая.
    """
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            if existing_app_id:
                set_clauses = []
                values = []
                
                fields_to_update = ['age', 'citizenship', 'region_name', 'address', 'phone']
                
                if username is not None and username != user_data.get('db_username'):
                    set_clauses.append("username = ?")
                    values.append(username)
                if full_name != user_data.get('db_full_name'):
                    set_clauses.append("full_name = ?")
                    values.append(full_name)

                for field in fields_to_update:
                    if field in user_data:
                        set_clauses.append(f"{field} = ?")
                        values.append(user_data.get(field))
                
                if set_clauses:
                    set_query_part = ", ".join(set_clauses)
                    values.append(existing_app_id)
                    
                    query = f"UPDATE applications SET {set_query_part}, status = 'updated' WHERE id = ?"
                    await db.execute(query, tuple(values))
                    logger.info(f"Заявка #{existing_app_id} для пользователя {user_id} обновлена в БД.")
                else:
                    logger.info(f"Нет данных для обновления заявки #{existing_app_id}.")

            else:
                await db.execute(
                    """
                    INSERT INTO applications (user_id, username, full_name, age, citizenship, region_name, address, phone, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'new')
                    ON CONFLICT(user_id) DO UPDATE SET
                        username = excluded.username, full_name = excluded.full_name, age = excluded.age,
                        citizenship = excluded.citizenship, region_name = excluded.region_name, address = excluded.address,
                        phone = excluded.phone, status = 'updated_conflict', updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        user_id, username, full_name, user_data.get('age'), user_data.get('citizenship'),
                        user_data.get('region_name'), user_data.get('address'), user_data.get('phone')
                    )
                )
                logger.info(f"Новая заявка от пользователя {user_id} добавлена/обновлена в БД.")
            await db.commit()
    except aiosqlite.Error as e:
        logger.error(f"Ошибка при добавлении/обновлении заявки для user_id {user_id}: {e}", exc_info=True)


async def get_applications_paginated(
    page: int = 1,
    per_page: int = 3,
    status_filter: list[str] | None = None
) -> tuple[list[tuple], int, int]:
    """
    Получает заявки из базы данных с поддержкой пагинации и фильтрации по статусу.

    Returns:
        Кортеж (список заявок, общее кол-во страниц, общее кол-во заявок).
    """
    if status_filter is None:
        status_filter = ['new', 'updated', 'updated_conflict']
    
    logger.info(f"Запрос заявок: страница {page}, {per_page}/страница, статусы: {status_filter}")

    offset = (page - 1) * per_page
    
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            placeholders = ','.join('?' for _ in status_filter)
            count_query = f"SELECT COUNT(*) FROM applications WHERE status IN ({placeholders})"
            
            async with db.execute(count_query, tuple(status_filter)) as cursor:
                total_items_tuple = await cursor.fetchone()
                total_items = total_items_tuple[0] if total_items_tuple else 0

            if total_items == 0:
                logger.info("Не найдено заявок, соответствующих фильтру.")
                return [], 0, 0

            total_pages = ceil(total_items / per_page)

            query = f"""
                SELECT id, user_id, username, full_name, age, citizenship,
                       region_name, address, phone, status, created_at, updated_at
                FROM applications WHERE status IN ({placeholders})
                ORDER BY updated_at DESC LIMIT ? OFFSET ?
            """
            params = tuple(status_filter) + (per_page, offset)
            
            async with db.execute(query, params) as cursor:
                applications_on_page = await cursor.fetchall()
                logger.info(f"Найдено {len(applications_on_page)} заявок на странице {page} (всего: {total_items}).")
                return applications_on_page, total_pages, total_items
    except aiosqlite.Error as e:
        logger.error(f"Ошибка при получении пагинированных заявок: {e}", exc_info=True)
        return [], 0, 0


async def get_application_by_id(app_id: int) -> tuple | None:
    """
    Получает одну заявку из базы данных по ее уникальному ID.

    Args:
        app_id: Первичный ключ (ID) заявки в таблице.

    Returns:
        Кортеж с данными заявки, если она найдена, иначе None.
    """
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            async with db.execute(
                "SELECT id, user_id, username, full_name, age, citizenship, region_name, address, phone, status, created_at, updated_at FROM applications WHERE id = ?",
                (app_id,)
            ) as cursor:
                application = await cursor.fetchone()
                if application:
                    logger.info(f"Найдена заявка по app_id: {app_id}.")
                else:
                    logger.warning(f"Заявка с app_id: {app_id} не найдена.")
                return application
    except aiosqlite.Error as e:
        logger.error(f"Ошибка при поиске заявки по app_id {app_id}: {e}", exc_info=True)
        return None


async def update_application_status(app_id: int, new_status: str, admin_id: int | None = None):
    """
    Обновляет статус указанной заявки.

    Args:
        app_id: ID заявки, статус которой нужно обновить.
        new_status: Новый статус для заявки (например, 'approved', 'rejected').
        admin_id: ID администратора, выполняющего действие (для логирования).
    """
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            await db.execute("UPDATE applications SET status = ? WHERE id = ?", (new_status, app_id))
            await db.commit()
        logger.info(f"Статус заявки #{app_id} обновлен на '{new_status}' администратором {admin_id or 'N/A'}.")
    except aiosqlite.Error as e:
        logger.error(f"Ошибка при обновлении статуса заявки #{app_id} на '{new_status}': {e}", exc_info=True)


async def add_to_banlist(user_id: int, reason: str):
    """
    Добавляет пользователя в список заблокированных (бан-лист).

    Args:
        user_id: ID пользователя, которого нужно заблокировать.
        reason: Причина блокировки.
    """
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            await db.execute("INSERT INTO blocked_users (user_id, reason) VALUES (?, ?)", (user_id, reason))
            await db.commit()
        logger.info(f"Пользователь {user_id} добавлен в бан-лист. Причина: {reason}")
    except aiosqlite.Error as e:
        logger.error(f"Ошибка при добавлении пользователя {user_id} в бан-лист: {e}", exc_info=True)


async def get_banlist() -> set[int]:
    """
    Получает множество ID всех заблокированных пользователей.

    Returns:
        Множество (set) с уникальными идентификаторами (user_id) заблокированных пользователей.
    """
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            async with db.execute("SELECT user_id FROM blocked_users") as cursor:
                return {row[0] for row in await cursor.fetchall()}
    except aiosqlite.Error as e:
        logger.error(f"Ошибка при получении бан-листа: {e}", exc_info=True)
        return set()