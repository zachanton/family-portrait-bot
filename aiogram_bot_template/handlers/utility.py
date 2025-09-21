# aiogram_bot_template/handlers/utility.py
import asyncio
import asyncpg
import structlog
from aiogram import Router, F
from aiogram.filters import StateFilter, Command
from aiogram.types import Message
from aiogram.utils.i18n import gettext as _

from aiogram_bot_template.data import texts
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.states.user import Generation
from aiogram_bot_template.db.db_api.storages import PostgresConnection
from aiogram_bot_template.db.repo import analytics

router = Router(name="utility-handlers")


@router.message(Command("help"))
async def help_cmd(msg: Message) -> None:
    await msg.answer(
        _("If you have any questions or need assistance, please contact our support team at: {email}").format(
            email=settings.bot.support_email
        )
    )


async def send_text_parts(msg: Message, text_parts: list[str]):
    """Sends a list of text parts as separate messages with a small delay."""
    for part in text_parts:
        await msg.answer(
            part.format(support_email=settings.bot.support_email),
            parse_mode="HTML"
        )
        await asyncio.sleep(0.3)


@router.message(Command("privacy"))
async def privacy(msg: Message, locale: str) -> None:
    """Handles the /privacy command by sending the policy in parts."""
    locale_texts = texts.get_texts(locale)
    await send_text_parts(msg, locale_texts.privacy_policy)


@router.message(Command("terms"))
async def terms(msg: Message, locale: str) -> None:
    """Handles the /terms command by sending the terms in parts."""
    locale_texts = texts.get_texts(locale)
    await send_text_parts(msg, locale_texts.terms_of_service)


@router.message(
    StateFilter(
        Generation.waiting_for_quality,
        Generation.waiting_for_next_action,
        Generation.waiting_for_feedback,
    ),
    F.text | F.photo | F.sticker | F.video | F.document | F.animation,
)
async def handle_unexpected_input_in_button_states(msg: Message) -> None:
    """
    Catches any user input when the bot expects a button press
    and gently guides the user back to the interface.
    """
    await msg.answer(
        _(
            "It looks like I'm waiting for you to make a choice. "
            "If you want to start over, just send /cancel."
        )
    )


@router.message(Command("stats"))
async def get_stats(msg: Message, db_pool: asyncpg.Pool) -> None:
    """Admin command to get business analytics."""
    if not msg.from_user or msg.from_user.id != settings.bot.admin_id:
        return

    db = PostgresConnection(db_pool, logger=structlog.get_logger())

    stats_24h = await analytics.get_summary_statistics(db, 1)
    stats_7d = await analytics.get_summary_statistics(db, 7)

    def format_section(title: str, s: analytics.AnalyticsData) -> str:
        def get_conv(current_step: int, prev_step: int) -> str:
            if prev_step == 0: return "(--%)"
            current_step = min(current_step, prev_step)
            rate = (current_step / prev_step) * 100
            return f"({rate:.1f}%)"

        funnel = s.funnel
        total_paid_generations = s.paid_tier_usage.quality_1 + s.paid_tier_usage.quality_2 + s.paid_tier_usage.quality_3

        def get_tier_percent(tier_count: int) -> str:
            if total_paid_generations == 0: return "(0%)"
            return f"({(tier_count / total_paid_generations) * 100:.1f}%)"

        return (
            f"<b>📊 {title}</b>\n\n"
            f"👤 <b>New Users:</b> {s.new_users}\n\n"
            f"<b>--- 🚀 Funnel ---</b>\n"
            f"<b>1. Photos Uploaded:</b> {funnel.photos_collected}\n"
            f"<b>2. Quality Selected:</b> {funnel.quality_selected} {get_conv(funnel.quality_selected, funnel.photos_collected)}\n"
            f"<b>3. Reached Payment:</b> {funnel.awaiting_payment} {get_conv(funnel.awaiting_payment, funnel.quality_selected)}\n"
            f"<b>4. Paid:</b> {funnel.paid} {get_conv(funnel.paid, funnel.awaiting_payment)}\n"
            f"<b>5. Completed:</b> {funnel.completed} {get_conv(funnel.completed, funnel.paid)}\n\n"
            f"💳 <b>Overall Conversion (Paid/Started):</b> {get_conv(funnel.paid, funnel.photos_collected)}\n\n"
            f"<b>--- 🛠️ Feature Usage (Completed) ---</b>\n"
            f"<b>Group Photos:</b> {s.feature_usage.group_photo}\n\n"
            f"<b>--- 💎 Paid Tier Usage ---</b>\n"
            f"<b>Standard (Tier 1):</b> {s.paid_tier_usage.quality_1} {get_tier_percent(s.paid_tier_usage.quality_1)}\n"
            f"<b>Enhanced (Tier 2):</b> {s.paid_tier_usage.quality_2} {get_tier_percent(s.paid_tier_usage.quality_2)}\n"
            f"<b>Premium (Tier 3):</b> {s.paid_tier_usage.quality_3} {get_tier_percent(s.paid_tier_usage.quality_3)}\n\n"
            f"💰 <b>Revenue:</b> {s.revenue.total_stars} ⭐"
        )

    report_24h = format_section("Last 24 Hours", stats_24h)
    report_7d = format_section("Last 7 Days", stats_7d)

    final_report = f"{report_24h}\n\n<pre>--------------------</pre>\n\n{report_7d}"

    await msg.answer(final_report)