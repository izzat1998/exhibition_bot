"""
Common keyboard utilities for the bot.
"""

from aiogram.types import (
    KeyboardButton,
    ReplyKeyboardMarkup,
)


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """
    Returns the main keyboard with common commands that should be available at all times.
    """
    keyboard = [
        [
            KeyboardButton(text="🔄 Start"),
            KeyboardButton(text="❓ Help"),
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Select a command or type a message",
    )
