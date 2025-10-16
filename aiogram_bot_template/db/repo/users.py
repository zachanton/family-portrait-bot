# aiogram_bot_template/db/repo/users.py
from aiogram_bot_template.db.db_api.storages import PostgresConnection


async def add_or_update_user(  # noqa: PLR0913
    db: PostgresConnection,
    user_id: int,
    username: str | None,
    first_name: str,
    *,  # <-- Makes all subsequent arguments keyword-only
    language_code: str | None,
    referral_source: str | None = None,
) -> None:
    """
    Adds a user or updates their data, including last activity time.
    Referral source is only set on creation.
    """
    sql = """
        INSERT INTO users (user_id, username, first_name, language_code, referral_source, last_activity_at, status)
        VALUES ($1, $2, $3, $4, $5, NOW(), 'active')
        ON CONFLICT (user_id) DO UPDATE SET
            username = EXCLUDED.username,
            first_name = EXCLUDED.first_name,
            last_activity_at = NOW(),
            status = 'active';
    """
    await db.execute(
        sql, (user_id, username, first_name, language_code, referral_source)
    )


async def set_user_status(db: PostgresConnection, user_id: int, status: str) -> None:
    """Sets the status for a user (e.g., 'blocked')."""
    sql = "UPDATE users SET status = $1 WHERE user_id = $2;"
    await db.execute(sql, (status, user_id))


async def get_user_language(db: PostgresConnection, user_id: int) -> str | None:
    """
    Get the user's language code from the database.

    Returns:
        The language code (e.g., "en") or None if the user is not found.
    """
    sql = "SELECT language_code FROM users WHERE user_id = $1;"
    result = await db.fetchrow(sql, (user_id,))
    return result.data.get("language_code") if result.data else None


async def set_user_language(
    db: PostgresConnection, user_id: int, language_code: str
) -> None:
    """Sets the language for a user."""
    sql = "UPDATE users SET language_code = $1 WHERE user_id = $2;"
    await db.execute(sql, (language_code, user_id))


async def get_user_trial_status(db: PostgresConnection, user_id: int) -> bool:
    """
    Checks if the user has already used their free trial.

    Returns:
        True if the free trial has been used, otherwise False.
    """
    sql = "SELECT has_used_free_trial FROM users WHERE user_id = $1;"
    result = await db.fetchrow(sql, (user_id,))
    if result.data:
        return result.data.get("has_used_free_trial", False)
    return False


async def mark_free_trial_as_used(db: PostgresConnection, user_id: int) -> None:
    """Marks the user's free trial as used."""
    sql = "UPDATE users SET has_used_free_trial = TRUE WHERE user_id = $1;"
    await db.execute(sql, (user_id,))


# --- NEW FUNCTIONS ---
async def get_user_live_queue_status(db: PostgresConnection, user_id: int) -> bool:
    """
    Checks if the user has already used their live queue slot.

    Returns:
        True if the live queue slot has been used, otherwise False.
    """
    # sql = "SELECT has_used_live_queue FROM users WHERE user_id = $1;"
    # result = await db.fetchrow(sql, (user_id,))
    # if result.data:
    #     return result.data.get("has_used_live_queue", False)
    return False


async def mark_live_queue_as_used(db: PostgresConnection, user_id: int) -> None:
    """Marks the user's live queue slot as used."""
    sql = "UPDATE users SET has_used_live_queue = TRUE WHERE user_id = $1;"
    await db.execute(sql, (user_id,))