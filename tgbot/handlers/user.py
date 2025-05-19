from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from infrastructure.some_api.api import MyApi
from tgbot.config import load_config

user_router = Router()


@user_router.message(CommandStart())
async def user_start(message: Message):
    try:
        config = load_config()
        async with MyApi(config=config) as api:
            status, result = await api.login(telegram_id=message.from_user.id)
            if status == 200:
                # User is already registered
                await message.answer(
                    f"""
👋 Welcome back, {message.from_user.first_name}!

📝 <b>How to use this bot:</b>
1️⃣ Type /lead to start collecting information about a potential lead
2️⃣ Send a photo of your business card when prompted
3️⃣ Follow the guided process to complete the lead form

Need help? Type /help to see all available commands.
                    """,
                    parse_mode="HTML",
                )
            else:
                # User needs to register first
                await message.answer(
                    f"""
👋 Hello {message.from_user.first_name}!

Welcome to the Exhibition Lead Collection Bot. 
Before you can start collecting leads, you need to register with your company.
                    """
                )
                # Show company selection for registration
                await show_company_selection(message, api)
    except Exception as e:
        await message.answer("An error occurred. Please try again later.")
        print(f"Error in user_start: {e}")


@user_router.message(Command("help"))
async def help_command(message: Message):
    help_text = (
        "Available commands:\n"
        "/start - Start the bot\n"
        "/lead - Start the lead form\n"
        "/help - Show this help message"
    )
    await message.answer(help_text)


async def show_company_selection(message: Message, api: MyApi):
    status, companies = await api.get_companies()

    if status != 200 or not companies:
        await message.reply("Unable to fetch companies. Please try again later.")
        return

    # Create inline keyboard with companies
    keyboard = []
    for company in companies:
        company_id = company.get("id")
        company_name = company.get("name")
        if company_id and company_name:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        text=company_name, callback_data=f"company:{company_id}"
                    )
                ]
            )

    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.answer(
        "Please select a company to register with:", reply_markup=markup
    )


@user_router.callback_query(F.data.startswith("company:"))
async def register_with_company(callback: CallbackQuery):
    try:
        await callback.answer()  # Acknowledge the callback first

        # Extract company ID from callback data
        company_id = callback.data.split(":")[1]

        config = load_config()

        async with MyApi(config=config) as api:
            # Register user with selected company
            status, result = await api.register(
                telegram_id=callback.from_user.id, company_id=company_id
            )

            if status in (200, 201):
                # Edit the original message to remove the inline keyboard
                await callback.message.edit_text(
                    "✅ Registration successful! Welcome to the system.\n\n"
                    "You can now use the /lead command to start the lead form."
                )
            else:
                # Edit the original message to show the error with retry option
                keyboard = [
                    [
                        InlineKeyboardButton(
                            text="🔄 Try Again", callback_data="retry_registration"
                        )
                    ]
                ]
                markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
                await callback.message.edit_text(
                    "❌ Registration failed. Please try again.", reply_markup=markup
                )
    except Exception as e:
        print(f"Error in register_with_company: {e}")
        await callback.message.answer(
            "An error occurred during registration. Please try again."
        )


@user_router.callback_query(F.data == "retry_registration")
async def retry_registration(callback: CallbackQuery):
    """Handle retry registration button click."""
    await callback.answer()
    await callback.message.edit_reply_markup(
        reply_markup=None
    )  # Remove the retry button
    await show_company_selection(callback.message, MyApi(config=load_config()))
