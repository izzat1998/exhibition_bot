"""
Confirmation and submission handlers for the lead form.
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)  # Added IKM

from infrastructure.some_api.api import MyApi  # Ensure this path is correct
from tgbot.config import load_config  # Ensure this path is correct
from tgbot.states.lead_form import LeadForm  # Ensure this path is correct

from .core import generate_summary  # Import generate_summary to show filled data

confirmation_router = Router()


@confirmation_router.callback_query(F.data == "lead:confirm")
async def confirm_lead(callback: CallbackQuery, state: FSMContext):
    # Get the summary of filled data
    data = await state.get_data()
    summary_text = await generate_summary(data)

    # Edit the existing message to show processing state
    await callback.message.edit_text(
        f"{summary_text}\n\n<b>⏳ Processing...</b>\n\nSubmitting your lead information. Please wait.",
        parse_mode="HTML",
        reply_markup=None,  # Remove any existing buttons
    )

    data = await state.get_data()
    config = load_config()
    lead_data_payload = {
        "telegram_id": str(callback.from_user.id),
        "category_id": data.get("exhibition_id"),
        "full_name": data.get("full_name"),
        "position": data.get("position"),
        "phone_number": data.get("phone_number"),
        "email": data.get("email"),
        "company_name": data.get("company_name"),
        "sphere_of_activity": data.get("sphere_of_activity"),
        "company_type": data.get("company_type"),
        "cargo": data.get("cargo"),
        "mode_of_transport": data.get("mode_of_transport"),
        "shipment_volume": data.get("shipment_volume"),
        "shipment_directions": [
            int(d_id)
            for d_id in data.get("selected_directions", [])
            if str(d_id).isdigit()
        ],
        "comments": data.get("comments"),
        "meeting_place": data.get("meeting_place"),
    }

    status_code = 500  # Default to error
    api_response_msg = {"error": "Submission failed due to an unexpected issue."}

    async with MyApi(config=config) as api:
        try:
            business_card_photo_id = data.get("business_card_photo")
            photo_bytes = None
            if business_card_photo_id:
                try:
                    bot_instance = callback.bot
                    file_info = await bot_instance.get_file(business_card_photo_id)
                    photo_bytes = await bot_instance.download_file(file_info.file_path)
                except Exception as e_photo:
                    print(f"Error downloading business card photo: {e_photo}")
                    # Continue without the photo

            status_code, api_response_msg = await api.create_lead(
                lead_data_payload, photo_bytes
            )

        except Exception as e_submit:
            print(f"Error submitting lead to API: {e_submit}")
            api_response_msg = {"error": f"API submission error: {e_submit}"}

    # Update the same message with result
    if status_code in (200, 201):
        await callback.message.edit_text(
            f"{summary_text}\n\n<b>✅ Success!</b>\n\n"
            "Thank you! The lead information has been submitted successfully.",
            parse_mode="HTML",
        )
    else:
        error_detail = api_response_msg.get("detail") or api_response_msg.get(
            "error", "Unknown error"
        )
        await callback.message.edit_text(
            f"{summary_text}\n\n<b>❌ Error!</b>\n\n"
            "There was a problem submitting the lead information.\n\n"
            f"<b>Error:</b> {error_detail}\n\n"
            "Please try again or contact support if the issue persists.",
            parse_mode="HTML",
        )

    await state.clear()
    await callback.answer()


@confirmation_router.callback_query(F.data == "lead:cancel")
async def cancel_lead(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "<b>❌ Cancelled</b>\n\nLead submission cancelled. You can start again with the /lead command.",
        parse_mode="HTML",
    )
    await state.clear()
    await callback.answer()


@confirmation_router.callback_query(F.data == "lead:restart")
async def restart_lead_form(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.update_data(ocr_processed=False, extracted_data={})  # Reset OCR flags

    # Send initial message for business card step (Option B from previous discussion)
    await callback.message.edit_reply_markup(
        reply_markup=None
    )  # Remove buttons from previous summary
    await callback.message.answer(
        "📋 <b>Lead Information Form Restarted</b>\n\n"
        "Let's start by uploading your business card for automatic information extraction.\n\n"
        "<b>Step 1/14:</b> Please upload a photo of your business card, or type 'skip' to fill the form manually.",
        parse_mode="HTML",
    )
    await state.set_state(LeadForm.business_card_photo)
    await callback.answer("Restarting the form...")
