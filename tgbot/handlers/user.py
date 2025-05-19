from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardRemove,
)

from infrastructure.some_api.api import MyApi
from tgbot.config import load_config
from tgbot.utils.keyboards import get_main_keyboard

user_router = Router()

# Define text patterns for button messages
START_BUTTON_PATTERNS = ["🔄 Start", "Start"]
LEAD_BUTTON_PATTERNS = ["📋 Lead", "Lead"]
HELP_BUTTON_PATTERNS = ["❓ Help", "Help"]


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
2️⃣ Send a photo of your business card when prompted:
   • 📎 Tap the paperclip icon at the bottom
   • 📷 Select "Photo" or "Gallery"
   • ✅ Choose your business card photo
   • ➡️ Send the photo
3️⃣ Follow the guided process to complete the lead form

Need help? Type /help to see all available commands.
                    """,
                    parse_mode="HTML",
                    reply_markup=get_main_keyboard(),
                )
            else:
                # User needs to register first
                await message.answer(
                    f"""
👋 Hello {message.from_user.first_name}!

Welcome to the Exhibition Lead Collection Bot. 
Before you can start collecting leads, you need to register with your company.

<b>After registration, you'll be able to:</b>
• 📸 Send business card photos
• 📋 Fill out lead forms
• 📊 Track your exhibition leads
                    """,
                    parse_mode="HTML",
                    reply_markup=ReplyKeyboardRemove(),
                )
                # Show company selection for registration
                await show_company_selection(message, api)
    except Exception as e:
        await message.answer("An error occurred. Please try again later.")
        print(f"Error in user_start: {e}")


@user_router.message(Command("help"))
async def help_command(message: Message):
    help_text = """
🌟 <b>Exhibition Lead Collection Bot</b> - Help Center

<u>Quick Start Guide</u>

🚀 <b>Getting Started</b>
• <code>/start</code> - Begin your session
• <code>/help</code>  - Show this help message anytime

📊 <b>Collecting Leads</b>
• <code>/lead</code> - Start a new lead collection
  - Take a photo of a business card
  - Or manually enter details
  - Follow the simple form

✨ <b>Pro Tips</b>
• Use natural light when photographing business cards
• Ensure all text is clear and visible in photos
• You can edit any information after scanning

📞 <b>Need Help?</b>
Contact our support team:
📧 izzatbek.khamraev@interrail.ag

🔍 <b>Quick Actions</b>
• Restart bot: <code>/start</code>
• New lead: <code>/lead</code>
• Show help: <code>/help</code>
"""
    await message.answer(help_text, parse_mode="HTML", reply_markup=get_main_keyboard())


async def show_company_selection(message: Message, api: MyApi):
    status, companies = await api.get_companies()

    if status != 200 or not companies:
        await message.answer("Unable to fetch companies. Please try again later.")
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
                # Send a new message with the main keyboard
                await callback.message.answer(
                    "Use the buttons below for quick access to commands:",
                    reply_markup=get_main_keyboard(),
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


# Button text handlers
@user_router.message(F.text.in_(START_BUTTON_PATTERNS))
async def handle_start_button(message: Message):
    """Handle 'Start' button text as /start command"""
    await user_start(message)


@user_router.message(F.text.in_(LEAD_BUTTON_PATTERNS))
async def handle_lead_button(message: Message):
    """Handle 'Lead' button text by directly invoking the lead command handler"""
    # Get the state for this user
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.memory import MemoryStorage

    # Import the lead command handler
    from tgbot.handlers.lead.business_card import cmd_lead

    # Get the bot instance
    bot = message.bot

    # Create a state context for this user
    storage = bot.fsm_storage or MemoryStorage()
    state = FSMContext(
        storage=storage, bot=bot, chat_id=message.chat.id, user_id=message.from_user.id
    )

    # Directly invoke the lead command handler
    await cmd_lead(message, state)


@user_router.message(F.text.in_(HELP_BUTTON_PATTERNS))
async def handle_help_button(message: Message):
    """Handle 'Help' button text as /help command"""
    await help_command(message)
