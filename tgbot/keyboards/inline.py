"""Reusable inline‑keyboard helpers."""

from typing import List, Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

BACK_BTN = InlineKeyboardButton(text="⬅️ Back", callback_data="lead:back")


def back_markup(
    extra_rows: Sequence[List[InlineKeyboardButton]] | None = None,
) -> InlineKeyboardMarkup:
    rows = [*extra_rows] if extra_rows else []
    rows.append([BACK_BTN])
    return InlineKeyboardMarkup(inline_keyboard=rows)
