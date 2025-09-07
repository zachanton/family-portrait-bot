# aiogram_bot_template/db/repo/payments.py
import json

from aiogram.types import SuccessfulPayment

from aiogram_bot_template.db.db_api.storages import PostgresConnection


async def log_successful_payment(
    db: PostgresConnection, user_id: int, request_id: int, payment: SuccessfulPayment
) -> None:
    """Logs a successful payment and links it to a generation request."""
    sql = """
        INSERT INTO payments (
            user_id, request_id, telegram_charge_id,
            provider_charge_id, currency, amount, invoice_payload
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (telegram_charge_id) DO NOTHING;
    """
    await db.execute(
        sql,
        (
            user_id,
            request_id,
            payment.telegram_payment_charge_id,
            payment.provider_payment_charge_id,
            payment.currency,
            payment.total_amount,
            json.loads(payment.invoice_payload),
        ),
    )
