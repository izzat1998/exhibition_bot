from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
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
HELP_BUTTON_PATTERNS = ["❓ Help", "Help"]
LEAD_BUTTON_PATTERNS = ["📝 New Lead", "Lead"]


# Define states for registration flow
class RegistrationStates(StatesGroup):
    waiting_for_first_name = State()
    waiting_for_last_name = State()
    waiting_for_registration = State()


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
async def register_with_company(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.answer()  # Acknowledge the callback first

        # Extract company ID from callback data
        company_id = callback.data.split(":")[1]

        # Store company_id in state for later use
        await state.update_data(company_id=company_id)

        # Check if first_name is missing
        if not callback.from_user.first_name:
            await state.set_state(RegistrationStates.waiting_for_first_name)
            await callback.message.answer("Please enter your first name:")
            return

        # Check if last_name is missing
        if not callback.from_user.last_name:
            # Store first_name in state
            await state.update_data(first_name=callback.from_user.first_name)
            await state.set_state(RegistrationStates.waiting_for_last_name)
            await callback.message.answer("Please enter your last name:")
            return

        # If both first_name and last_name are available, proceed with registration
        await complete_registration(
            callback.message,
            callback.from_user.id,
            company_id,
            callback.from_user.first_name,
            callback.from_user.last_name,
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
async def handle_lead_button(message: Message, state: FSMContext = None):
    """Handle 'Lead' button text as /lead command"""
    # Import cmd_lead from the business_card module
    from tgbot.handlers.lead.business_card import cmd_lead

    await cmd_lead(message, state)


@user_router.message(F.text.in_(HELP_BUTTON_PATTERNS))
async def handle_help_button(message: Message):
    """Handle 'Help' button text as /help command"""
    await help_command(message)


# Handlers for registration state machine
@user_router.message(RegistrationStates.waiting_for_first_name)
async def process_first_name(message: Message, state: FSMContext):
    """Process the first name provided by the user"""
    # Store the first name
    first_name = message.text.strip()
    if not first_name:
        await message.answer("Please enter a valid first name:")
        return

    await state.update_data(first_name=first_name)

    # Check if we also need last name
    await state.set_state(RegistrationStates.waiting_for_last_name)
    await message.answer("Please enter your last name:")


@user_router.message(RegistrationStates.waiting_for_last_name)
async def process_last_name(message: Message, state: FSMContext):
    """Process the last name provided by the user"""
    # Store the last name
    last_name = message.text.strip()
    if not last_name:
        await message.answer("Please enter a valid last name:")
        return

    # Get all stored data
    data = await state.get_data()
    first_name = data.get("first_name")
    company_id = data.get("company_id")

    # Clear the state
    await state.clear()

    # Complete the registration
    await complete_registration(
        message, message.from_user.id, company_id, first_name, last_name
    )


async def complete_registration(
    message, telegram_id, company_id, first_name, last_name
):
    """Complete the registration process with the API"""
    config = load_config()

    async with MyApi(config=config) as api:
        # Register user with selected company
        status, result = await api.register(
            telegram_id=telegram_id,
            company_id=company_id,
            first_name=first_name,
            last_name=last_name,
        )

        if status in (200, 201):
            # Registration successful
            await message.answer(
                "✅ Registration successful! Welcome to the system.\n\n"
                "You can now use the /lead command to start the lead form."
            )
            # Send a new message with the main keyboard
            await message.answer(
                "Use the buttons below for quick access to commands:",
                reply_markup=get_main_keyboard(),
            )
        else:
            # Registration failed
            keyboard = [
                [
                    InlineKeyboardButton(
                        text="🔄 Try Again", callback_data="retry_registration"
                    )
                ]
            ]
            markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
            await message.answer(
                "❌ Registration failed. Please try again.", reply_markup=markup
            )
