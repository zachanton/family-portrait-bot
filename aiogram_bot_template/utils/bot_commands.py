# aiogram_bot_template/utils/bot_commands.py
from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault

from aiogram_bot_template.data import texts


async def set_bot_commands(bot: Bot) -> None:
    """
    Sets up the bot commands for all supported languages from the texts package.
    """
    for lang_code, lang_texts in texts.ALL_TEXTS.items():
        bot_commands = [
            BotCommand(command=cmd.command, description=cmd.description)
            for cmd in lang_texts.commands
        ]
        await bot.set_my_commands(
            bot_commands,
            scope=BotCommandScopeDefault(),
            language_code=lang_code
        )


async def set_bot_description(bot: Bot) -> None:
    """
    Sets up the bot's description for all supported languages from the texts package.
    """
    for lang_code, lang_texts in texts.ALL_TEXTS.items():
        await bot.set_my_description(
            description=lang_texts.bot_info.description,
            language_code=lang_code
        )
        await bot.set_my_short_description(
            short_description=lang_texts.bot_info.short_description,
            language_code=lang_code
        )