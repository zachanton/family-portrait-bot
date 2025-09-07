# aiogram_bot_template/db/repo/feedback.py
from aiogram_bot_template.db.db_api.storages import PostgresConnection


async def add_feedback(
    db: PostgresConnection, user_id: int, generation_id: int, rating: str
) -> None:
    """
    Adds a feedback record for a specific generation.
    If a feedback record for this generation already exists, it does nothing.

    Args:
        db: The database connection.
        user_id: The ID of the user providing feedback.
        generation_id: The ID of the generation being rated.
        rating: The rating given by the user ('like' or 'dislike').
    """
    sql = """
        INSERT INTO feedback (user_id, generation_id, rating)
        VALUES ($1, $2, $3)
        ON CONFLICT (generation_id) DO NOTHING;
    """
    await db.execute(sql, (user_id, generation_id, rating))
