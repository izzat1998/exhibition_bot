"""
Business card photo handling and form initialization.
"""

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from infrastructure.some_api.api import MyApi  # Ensure this path is correct
from tgbot.config import load_config  # Ensure this path is correct
from tgbot.states.lead_form import LeadForm  # Ensure this path is correct

from .core import (
    generate_summary,
    is_valid_email,
    is_valid_phone,
    truncate_for_callback,
)  # Relative import

# Define callback data limits from navigation.py or centrally
SUGGESTION_VALUE_MAX_BYTES = {
    "name": 38,
    "position": 30,
    "phone": 35,
    "email": 35,
    "company": 30,
}

business_card_router = Router()


async def show_summary(message: Message, state: FSMContext):
    """Show a summary of the collected lead information."""
    data = await state.get_data()
    summary_text = await generate_summary(data)
    final_text = f"{summary_text}\n\n<b>✅ Lead Information Complete</b>\n\nPlease review the information above and confirm if it's correct."
    keyboard_rows = [
        [InlineKeyboardButton(text="✅ Confirm", callback_data="lead:confirm")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="lead:cancel")],
        [InlineKeyboardButton(text="🔄 Restart", callback_data="lead:restart")],
    ]
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    await message.answer(final_text, parse_mode="HTML", reply_markup=markup)


@business_card_router.message(Command(commands=["lead"]))
async def cmd_lead(message: Message, state: FSMContext):
    """Start the lead form collection process."""
    await state.clear()
    await state.update_data(ocr_processed=False, extracted_data={})
    await message.answer(
        "📋 <b>Lead Information Form</b>\n\n"
        "Let's start by uploading your business card for automatic information extraction.\n\n"
        "<b>Step 1/14:</b> Please upload a photo of your business card, or type 'skip' to fill the form manually.",
        parse_mode="HTML",
    )
    await state.set_state(LeadForm.business_card_photo)


@business_card_router.message(
    StateFilter(LeadForm.business_card_photo),
    F.text.func(lambda text: text and text.lower() == "skip"),
)
async def skip_business_card_text(message: Message, state: FSMContext):
    """Skip the business card photo upload via text."""
    data = await state.get_data()
    # Check if it's an initial skip (no other data collected beyond OCR flags)
    is_initial_skip = not any(
        key in data
        for key in [
            "full_name",
            "position",
            "phone_number",
            "email",
            "company_name",
            "sphere_of_activity",
            "company_type",
            "cargo",
            "mode_of_transport",
            "shipment_volume",
            "selected_directions",
            "comments",
            "meeting_place",
        ]
    )

    if is_initial_skip:
        await state.update_data(
            business_card_photo=None,
            ocr_processed=False,
            business_card_skipped=True,
            extracted_data={},
        )
        await message.answer(
            "<b>Manual form filling selected.</b>\n\nLet's proceed with the form step by step.",
            parse_mode="HTML",
        )

        # Prompt for full name (Step 2)
        keyboard = [[InlineKeyboardButton(text="⬅️ Back", callback_data="lead:back")]]
        # Check if there was a "full_name" from a previous attempt before skip, though unlikely here
        extracted_data = data.get("extracted_data", {})
        if data.get("ocr_processed") and extracted_data.get(
            "full_name"
        ):  # Should be false if initial skip
            val = extracted_data.get("full_name")
            safe_val = truncate_for_callback(val, SUGGESTION_VALUE_MAX_BYTES["name"])
            keyboard.insert(
                0,
                [
                    InlineKeyboardButton(
                        text=f"Use: {val}",
                        callback_data=f"use_suggestion:name:{safe_val}",
                    )
                ],
            )

        markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await message.answer(
            "<b>Step 2/14:</b> What is your full name?",
            parse_mode="HTML",
            reply_markup=markup,
        )
        await state.set_state(LeadForm.full_name)
    else:  # Final skip (at the end of the form)
        await state.update_data(
            business_card_photo=None
        )  # business_card_skipped might already be true or false
        await message.answer("Business card photo upload skipped.")
        await show_summary(message, state)


@business_card_router.callback_query(
    LeadForm.business_card_photo, F.data == "business_card:skip"
)
async def skip_business_card_button(callback: CallbackQuery, state: FSMContext):
    """Skip the business card photo upload using the inline button (at the end of form)."""
    await state.update_data(
        business_card_photo=None
    )  # business_card_skipped might be true or false
    await callback.message.edit_reply_markup(reply_markup=None)  # Remove skip button
    await callback.message.answer("Business card photo upload skipped.")
    await callback.answer()
    await show_summary(callback.message, state)


@business_card_router.message(StateFilter(LeadForm.business_card_photo), F.photo)
async def process_business_card_photo(message: Message, state: FSMContext):
    """Process the business card photo (can be at start or end of form)."""
    processing_msg = await message.answer(
        "<b>⏳ Processing business card...</b> This may take a moment.",
        parse_mode="HTML",
    )
    photo_id = message.photo[-1].file_id

    # If this photo is submitted at the end, previous data exists.
    # If at the start, data is minimal.
    await state.update_data(
        business_card_photo=photo_id, business_card_skipped=False
    )  # Explicitly not skipped

    config = load_config()
    extracted_data_from_ocr = {}
    ocr_success = False

    try:
        bot = message.bot
        file = await bot.get_file(photo_id)
        file_content = await bot.download_file(file.file_path)
        async with MyApi(config=config) as api:
            ocr_status, ocr_response = await api.business_card_photo_ocr(file_content)

        if ocr_status == 200 and ocr_response and ocr_response.get("extracted_data"):
            extracted_data_from_ocr = ocr_response.get("extracted_data", {})
            ocr_success = True
            await state.update_data(
                extracted_data=extracted_data_from_ocr, ocr_processed=True
            )

    except Exception as e:
        print(f"Error processing business card photo: {e}")
        # No need to set ocr_processed to True here

    await processing_msg.delete()

    current_data = await state.get_data()
    # Check if this is an initial upload (minimal other data fields present)
    is_initial_upload = not any(
        key in current_data
        for key in [
            "full_name",
            "position",
            "phone_number",
            "email",
            "company_name",  # etc.
            "meeting_place",  # Meeting place is the last step before final business card prompt
        ]
        if key
        not in [
            "business_card_photo",
            "ocr_processed",
            "extracted_data",
            "business_card_skipped",
        ]
    )

    if not ocr_success or not extracted_data_from_ocr:
        await message.answer(
            "<b>⚠️ Could not extract information from the business card.</b>",
            parse_mode="HTML",
        )
        if is_initial_upload:
            await message.answer(
                "Let's fill in the form manually.\n\n<b>Step 2/14:</b> What is your full name?",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="⬅️ Back", callback_data="lead:back")]
                    ]
                ),
            )
            await state.set_state(LeadForm.full_name)
        else:  # OCR failed at the end of the form
            await show_summary(message, state)
        return

    # OCR Succeeded
    extracted_fields_summary = []
    if extracted_data_from_ocr.get("full_name"):
        extracted_fields_summary.append(
            f"📝 Name: {extracted_data_from_ocr['full_name']}"
        )
    if extracted_data_from_ocr.get("position"):
        extracted_fields_summary.append(
            f"🏢 Position: {extracted_data_from_ocr['position']}"
        )
    phone = extracted_data_from_ocr.get("phone") or extracted_data_from_ocr.get(
        "phone_number"
    )
    if phone:
        extracted_fields_summary.append(f"📱 Phone: {phone}")
    if extracted_data_from_ocr.get("email"):
        extracted_fields_summary.append(f"📧 Email: {extracted_data_from_ocr['email']}")
    if extracted_data_from_ocr.get("company_name"):
        extracted_fields_summary.append(
            f"🏭 Company: {extracted_data_from_ocr['company_name']}"
        )

    if is_initial_upload:
        # Auto-fill valid data if initial upload
        if extracted_data_from_ocr.get("full_name"):
            await state.update_data(full_name=extracted_data_from_ocr.get("full_name"))
        if extracted_data_from_ocr.get("position"):
            await state.update_data(position=extracted_data_from_ocr.get("position"))
        if phone and is_valid_phone(phone):
            await state.update_data(phone_number=phone)
        if extracted_data_from_ocr.get("email") and is_valid_email(
            extracted_data_from_ocr.get("email")
        ):
            await state.update_data(email=extracted_data_from_ocr.get("email"))
        if extracted_data_from_ocr.get("company_name"):
            await state.update_data(
                company_name=extracted_data_from_ocr.get("company_name")
            )

        # Store all_fields_present for ocr:confirm logic
        all_contact_fields_present = (
            bool(extracted_data_from_ocr.get("full_name"))
            and bool(extracted_data_from_ocr.get("position"))
            and (phone and is_valid_phone(phone))
            and (
                extracted_data_from_ocr.get("email")
                and is_valid_email(extracted_data_from_ocr.get("email"))
            )
            and bool(extracted_data_from_ocr.get("company_name"))
        )
        await state.update_data(all_contact_fields_present=all_contact_fields_present)

        ocr_summary_text = "\n".join(extracted_fields_summary)
        keyboard = [
            [
                InlineKeyboardButton(
                    text="✅ Confirm and Continue", callback_data="ocr:confirm"
                )
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Edit Step by Step", callback_data="ocr:step_by_step"
                )
            ],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="lead:back")],
        ]
        markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await message.answer(
            f"<b>✅ Information extracted:</b>\n\n{ocr_summary_text}\n\nPlease confirm or choose to edit.",
            parse_mode="HTML",
            reply_markup=markup,
        )
        await state.set_state("ocr_confirmation")  # Transient state
    else:  # Business card uploaded at the end of the form
        await message.answer(
            f"<b>✅ Business card processed.</b> Extracted (for reference):\n"
            + "\n".join(extracted_fields_summary),
            parse_mode="HTML",
        )
        await show_summary(message, state)


@business_card_router.callback_query(F.data == "ocr:confirm")
async def ocr_confirm_cb(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state != "ocr_confirmation":
        await callback.answer("This action is not available right now.")
        return

    await callback.answer("Data confirmed! Proceeding...")
    await callback.message.edit_reply_markup(reply_markup=None)  # Clear buttons

    data = await state.get_data()
    summary = await generate_summary(data)  # Summary with auto-filled data

    # Determine next step based on what was auto-filled by OCR
    # If all_contact_fields_present (name, pos, valid phone, valid email, company), go to sphere.
    # Otherwise, go to the first non-filled/invalid field among these.

    next_step_message = ""
    next_fsm_state = None

    # This logic matches the one in the original process_business_card_initial's ocr:confirm part
    if data.get("all_contact_fields_present"):
        next_step_message = (
            f"{summary}\n\n<b>Step 7/14:</b> What is your company's sphere of activity?"
        )
        next_fsm_state = LeadForm.sphere_of_activity
    elif not data.get("full_name"):
        next_step_message = f"{summary}\n\n<b>Step 2/14:</b> What is your full name?"
        next_fsm_state = LeadForm.full_name
    elif not data.get("position"):
        next_step_message = (
            f"{summary}\n\n<b>Step 3/14:</b> What is your position in the company?"
        )
        next_fsm_state = LeadForm.position
    elif not data.get(
        "phone_number"
    ):  # This implies extracted phone was invalid or not present
        next_step_message = f"{summary}\n\n<b>Step 4/14:</b> What is your phone number?"
        next_fsm_state = LeadForm.phone_number
    elif not data.get("email"):  # Implies extracted email was invalid or not present
        next_step_message = (
            f"{summary}\n\n<b>Step 5/14:</b> What is your email address?"
        )
        next_fsm_state = LeadForm.email
    elif not data.get("company_name"):
        next_step_message = f"{summary}\n\n<b>Step 6/14:</b> What is your company name?"
        next_fsm_state = LeadForm.company_name
    else:  # Should be caught by all_contact_fields_present, but as a fallback
        next_step_message = (
            f"{summary}\n\n<b>Step 7/14:</b> What is your company's sphere of activity?"
        )
        next_fsm_state = LeadForm.sphere_of_activity

    reply_markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="lead:back")]
        ]
    )
    await callback.message.answer(
        next_step_message, parse_mode="HTML", reply_markup=reply_markup
    )
    await state.set_state(next_fsm_state)


@business_card_router.callback_query(F.data == "ocr:step_by_step")
async def ocr_step_by_step_cb(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state != "ocr_confirmation":
        await callback.answer("This action is not available right now.")
        return

    await callback.answer("Continuing with step-by-step process...")
    await callback.message.edit_reply_markup(reply_markup=None)

    data = await state.get_data()
    extracted_ocr_data = data.get("extracted_data", {})  # Keep this for suggestions
    ocr_was_processed_flag = data.get("ocr_processed", False)  # Keep this

    # Reset only the form fields that OCR might have auto-filled
    await state.update_data(
        full_name=None,
        position=None,
        phone_number=None,
        email=None,
        company_name=None,
        extracted_data=extracted_ocr_data,  # Preserve
        ocr_processed=ocr_was_processed_flag,  # Preserve
    )

    current_summary = await generate_summary(
        await state.get_data()
    )  # Will be mostly empty

    keyboard_rows = []
    # Add suggestion for full_name if available from OCR
    if ocr_was_processed_flag and extracted_ocr_data.get("full_name"):
        val = extracted_ocr_data.get("full_name")
        safe_val = truncate_for_callback(val, SUGGESTION_VALUE_MAX_BYTES["name"])
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text=f"Use: {val}", callback_data=f"use_suggestion:name:{safe_val}"
                )
            ]
        )
    keyboard_rows.append(
        [InlineKeyboardButton(text="⬅️ Back", callback_data="lead:back")]
    )
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await callback.message.answer(
        f"{current_summary}\n\n<b>Step 2/14:</b> What is your full name?",
        parse_mode="HTML",
        reply_markup=markup,
    )
    await state.set_state(LeadForm.full_name)


@business_card_router.callback_query(
    F.data.startswith("use_suggestion:")
)  # No specific state needed
async def use_suggestion_cb(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":", 2)  # Split only twice
    if len(parts) < 3:
        await callback.answer("Invalid suggestion format.", show_alert=True)
        return

    field_type = parts[1]
    value_from_cb = parts[2]

    data = await state.get_data()
    extracted_data_state = data.get("extracted_data", {})
    ocr_processed_state = data.get(
        "ocr_processed", True
    )  # Assume true if suggestion is used

    actual_value_to_use = value_from_cb
    if value_from_cb.endswith("...") and extracted_data_state.get(
        field_type if field_type != "company" else "company_name"
    ):
        if field_type == "name" and extracted_data_state.get("full_name"):
            actual_value_to_use = extracted_data_state.get("full_name")
        elif field_type == "position" and extracted_data_state.get("position"):
            actual_value_to_use = extracted_data_state.get("position")
        elif field_type == "phone" and (
            extracted_data_state.get("phone")
            or extracted_data_state.get("phone_number")
        ):
            actual_value_to_use = extracted_data_state.get(
                "phone"
            ) or extracted_data_state.get("phone_number")
        elif field_type == "email" and extracted_data_state.get("email"):
            actual_value_to_use = extracted_data_state.get("email")
        elif field_type == "company" and extracted_data_state.get("company_name"):
            actual_value_to_use = extracted_data_state.get("company_name")

    await callback.answer(
        f"{field_type.replace('_', ' ').title()} set to: {actual_value_to_use[:30]}..."
    )  # Show truncated in answer

    # Update state and prepare for next step
    updated_fields = {
        "extracted_data": extracted_data_state,  # Preserve
        "ocr_processed": ocr_processed_state,  # Preserve
    }
    next_prompt = ""
    next_fsm_state = None
    suggestion_for_next_step_field = None
    suggestion_for_next_step_value_cb = None

    if field_type == "name":
        updated_fields["full_name"] = actual_value_to_use
        next_prompt = "<b>Step 3/14:</b> What is your position in the company?"
        next_fsm_state = LeadForm.position
        if ocr_processed_state and extracted_data_state.get("position"):
            suggestion_for_next_step_field = "position"
            suggestion_for_next_step_value_cb = extracted_data_state.get("position")

    elif field_type == "position":
        updated_fields["position"] = actual_value_to_use
        next_prompt = "<b>Step 4/14:</b> What is your phone number?"
        next_fsm_state = LeadForm.phone_number
        phone_val = extracted_data_state.get("phone") or extracted_data_state.get(
            "phone_number"
        )
        if ocr_processed_state and phone_val:
            suggestion_for_next_step_field = "phone"
            suggestion_for_next_step_value_cb = phone_val

    elif field_type == "phone":
        updated_fields["phone_number"] = actual_value_to_use
        next_prompt = "<b>Step 5/14:</b> What is your email address?"
        next_fsm_state = LeadForm.email
        if ocr_processed_state and extracted_data_state.get("email"):
            suggestion_for_next_step_field = "email"
            suggestion_for_next_step_value_cb = extracted_data_state.get("email")

    elif field_type == "email":
        updated_fields["email"] = actual_value_to_use
        next_prompt = "<b>Step 6/14:</b> What is your company name?"
        next_fsm_state = LeadForm.company_name
        if ocr_processed_state and extracted_data_state.get("company_name"):
            suggestion_for_next_step_field = "company"
            suggestion_for_next_step_value_cb = extracted_data_state.get("company_name")

    elif field_type == "company":
        updated_fields["company_name"] = actual_value_to_use
        next_prompt = "<b>Step 7/14:</b> What is your company's sphere of activity?"
        next_fsm_state = LeadForm.sphere_of_activity
        # No typical OCR suggestion for sphere_of_activity

    else:
        await callback.message.answer(
            f"Unknown field type for suggestion: {field_type}"
        )
        return

    await state.update_data(**updated_fields)
    new_data = await state.get_data()
    summary_after_suggestion = await generate_summary(new_data)

    next_step_keyboard_rows = []
    if suggestion_for_next_step_field and suggestion_for_next_step_value_cb:
        max_b = SUGGESTION_VALUE_MAX_BYTES.get(suggestion_for_next_step_field, 30)
        safe_sugg_val = truncate_for_callback(suggestion_for_next_step_value_cb, max_b)
        next_step_keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text=f"Use: {suggestion_for_next_step_value_cb}",
                    callback_data=f"use_suggestion:{suggestion_for_next_step_field}:{safe_sugg_val}",
                )
            ]
        )
    next_step_keyboard_rows.append(
        [InlineKeyboardButton(text="⬅️ Back", callback_data="lead:back")]
    )
    next_step_markup = InlineKeyboardMarkup(inline_keyboard=next_step_keyboard_rows)

    await callback.message.edit_text(  # Edit the message that had the suggestion button
        f"{summary_after_suggestion}\n\n{next_prompt}",
        parse_mode="HTML",
        reply_markup=next_step_markup,
    )
    if next_fsm_state:
        await state.set_state(next_fsm_state)
