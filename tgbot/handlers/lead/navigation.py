"""
Navigation handlers for the lead form, including back button functionality.
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from tgbot.states.lead_form import LeadForm

from .core import (
    COMPANY_TYPE_CHOICES,
    MODE_OF_TRANSPORT_CHOICES,
    generate_summary,
    get_previous_state,
    truncate_for_callback,  # Import the new utility
)

navigation_router = Router()


# Define callback data limits (Telegram's limit is 64 bytes)
# Subtract prefix lengths to get available space for the value itself.
# Example: "use_suggestion:name:" is 20 bytes. Max value bytes = 64 - 20 = 44.
# Be conservative due to multi-byte characters.
SUGGESTION_VALUE_MAX_BYTES = {
    "name": 38,  # "use_suggestion:name:" + value
    "position": 30,  # "use_suggestion:position:" + value (more prefix)
    "phone": 35,  # "use_suggestion:phone:" + value
    "email": 35,  # "use_suggestion:email:" + value
    "company": 30,  # "use_suggestion:company:" + value
}


async def handle_back_navigation(message_or_callback, state: FSMContext):
    """Handle back navigation logic for both message and callback handlers."""
    current_fsm_state = await state.get_state()
    if not current_fsm_state:
        if isinstance(message_or_callback, CallbackQuery):
            await message_or_callback.answer("Cannot go back from this state.")
        return False

    current_state_name = current_fsm_state.split(":")[-1]
    prev_state_name = await get_previous_state(current_state_name)

    if not prev_state_name:
        msg_text = "You are at the first step already."
        if isinstance(message_or_callback, CallbackQuery):
            await message_or_callback.answer(msg_text, show_alert=True)
        else:
            await message_or_callback.answer(msg_text)
        return False

    data = await state.get_data()
    summary = await generate_summary(data)
    msg_to_edit_or_answer = (
        message_or_callback.message
        if isinstance(message_or_callback, CallbackQuery)
        else message_or_callback
    )

    extracted_data = data.get("extracted_data", {})
    ocr_processed = data.get("ocr_processed", False)

    await state.set_state(getattr(LeadForm, prev_state_name))

    keyboard_rows = []
    prompt_text = ""

    if prev_state_name == "business_card_photo":
        prompt_text = f"{summary}\n\n<b>Step 1/14:</b> Please upload a photo of the business card, or type 'skip' to fill the form manually."
        # No specific keyboard beyond what might be implicitly handled by photo/text input
        await msg_to_edit_or_answer.answer(
            prompt_text, parse_mode="HTML"
        )  # Send new message for this step

    elif prev_state_name == "full_name":
        prompt_text = f"{summary}\n\n<b>Step 2/14:</b> What is the full name?"
        if ocr_processed and extracted_data.get("full_name"):
            val = extracted_data.get("full_name")
            safe_val = truncate_for_callback(val, SUGGESTION_VALUE_MAX_BYTES["name"])
            keyboard_rows.append(
                [
                    InlineKeyboardButton(
                        text=f"Use: {val}",
                        callback_data=f"use_suggestion:name:{safe_val}",
                    )
                ]
            )

    elif prev_state_name == "position":
        prompt_text = (
            f"{summary}\n\n<b>Step 3/14:</b> What is the position in the company?"
        )
        if ocr_processed and extracted_data.get("position"):
            val = extracted_data.get("position")
            safe_val = truncate_for_callback(
                val, SUGGESTION_VALUE_MAX_BYTES["position"]
            )
            keyboard_rows.append(
                [
                    InlineKeyboardButton(
                        text=f"Use: {val}",
                        callback_data=f"use_suggestion:position:{safe_val}",
                    )
                ]
            )

    elif prev_state_name == "phone_number":
        prompt_text = f"{summary}\n\n<b>Step 4/14:</b> What is the phone number?"
        phone_val = extracted_data.get("phone") or extracted_data.get("phone_number")
        if ocr_processed and phone_val:
            safe_val = truncate_for_callback(
                phone_val, SUGGESTION_VALUE_MAX_BYTES["phone"]
            )
            keyboard_rows.append(
                [
                    InlineKeyboardButton(
                        text=f"Use: {phone_val}",
                        callback_data=f"use_suggestion:phone:{safe_val}",
                    )
                ]
            )

    elif prev_state_name == "email":
        prompt_text = f"{summary}\n\n<b>Step 5/14:</b> What is the email address?"
        if ocr_processed and extracted_data.get("email"):
            val = extracted_data.get("email")
            safe_val = truncate_for_callback(val, SUGGESTION_VALUE_MAX_BYTES["email"])
            keyboard_rows.append(
                [
                    InlineKeyboardButton(
                        text=f"Use: {val}",
                        callback_data=f"use_suggestion:email:{safe_val}",
                    )
                ]
            )

    elif prev_state_name == "company_name":
        prompt_text = f"{summary}\n\n<b>Step 6/14:</b> What is the company name?"
        if ocr_processed and extracted_data.get("company_name"):
            val = extracted_data.get("company_name")
            safe_val = truncate_for_callback(val, SUGGESTION_VALUE_MAX_BYTES["company"])
            keyboard_rows.append(
                [
                    InlineKeyboardButton(
                        text=f"Use: {val}",
                        callback_data=f"use_suggestion:company:{safe_val}",
                    )
                ]
            )

    elif prev_state_name == "sphere_of_activity":
        prompt_text = (
            f"{summary}\n\n<b>Step 7/14:</b> What is the company's sphere of activity?"
        )

    elif prev_state_name == "company_type":
        prompt_text = f"{summary}\n\n<b>Step 8/14:</b> What is the company type?"
        for value, label in COMPANY_TYPE_CHOICES:
            keyboard_rows.append(
                [
                    InlineKeyboardButton(
                        text=label, callback_data=f"company_type:{value}"
                    )
                ]
            )

    elif prev_state_name == "cargo":
        prompt_text = (
            f"{summary}\n\n<b>Step 9/14:</b> What type of cargo does company handle?"
        )

    elif prev_state_name == "mode_of_transport":
        prompt_text = (
            f"{summary}\n\n<b>Step 10/14:</b> What is the preferred mode of transport?"
        )
        for value, label in MODE_OF_TRANSPORT_CHOICES:
            keyboard_rows.append(
                [InlineKeyboardButton(text=label, callback_data=f"transport:{value}")]
            )

    elif prev_state_name == "shipment_volume":
        prompt_text = (
            f"{summary}\n\n<b>Step 11/14:</b> What is the monthly shipment volume?"
        )

    elif prev_state_name == "shipment_directions":
        prompt_text = f"{summary}\n\n<b>Step 12/14:</b> Please select the shipment directions (you can select multiple):"
        directions = data.get("available_directions", [])
        selected_directions_ids = data.get("selected_directions", set())
        if isinstance(selected_directions_ids, list):  # Ensure set of strings
            selected_directions_ids = {str(d_id) for d_id in selected_directions_ids}

        for direction in directions:
            direction_id_str = str(direction.get("id"))
            direction_name = direction.get("name")
            if direction_id_str and direction_name:
                prefix = "✅ " if direction_id_str in selected_directions_ids else ""
                keyboard_rows.append(
                    [
                        InlineKeyboardButton(
                            text=f"{prefix}{direction_name}",
                            callback_data=f"direction:{direction_id_str}",
                        )
                    ]
                )
        keyboard_rows.append(
            [InlineKeyboardButton(text="✅ Done", callback_data="directions:done")]
        )

    elif prev_state_name == "comments":
        prompt_text = f"{summary}\n\n<b>Step 13/14:</b> Do you have any additional comments? (Type 'none' if you don't have any)"

    elif prev_state_name == "meeting_place":
        prompt_text = (
            f"{summary}\n\n<b>Step 14/14:</b> Where did the meeting take place?"
        )
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text="Our Booth", callback_data="meeting_place:our_booth"
                )
            ]
        )
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text="Partner Booth", callback_data="meeting_place:partner_booth"
                )
            ]
        )

    # Add "Back" button to all applicable states' keyboards, except for the very first state.
    if (
        prev_state_name != "business_card_photo"
    ):  # No back button if we are at the first step
        # Check if the current state (before going back) has a previous state.
        # This ensures back button is added only if we are not at the very beginning.
        grand_prev_state = await get_previous_state(prev_state_name)
        if (
            grand_prev_state or prev_state_name == "full_name"
        ):  # full_name's prev is business_card_photo
            keyboard_rows.append(
                [InlineKeyboardButton(text="⬅️ Back", callback_data="lead:back")]
            )

    reply_markup = (
        InlineKeyboardMarkup(inline_keyboard=keyboard_rows) if keyboard_rows else None
    )

    if prompt_text:
        # Try to edit if it's a callback, otherwise send new message.
        # For business_card_photo, we always send a new message as per its specific handling above.
        if (
            isinstance(message_or_callback, CallbackQuery)
            and prev_state_name != "business_card_photo"
        ):
            try:
                await msg_to_edit_or_answer.edit_text(
                    prompt_text, parse_mode="HTML", reply_markup=reply_markup
                )
            except (
                Exception
            ):  # If edit fails (e.g. message too old, or not from bot), send new.
                await message_or_callback.message.answer(
                    prompt_text, parse_mode="HTML", reply_markup=reply_markup
                )
        elif (
            prev_state_name != "business_card_photo"
        ):  # For regular messages, not the initial step
            await msg_to_edit_or_answer.answer(
                prompt_text, parse_mode="HTML", reply_markup=reply_markup
            )

    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.answer("Moved back to the previous step.")
    return True


@navigation_router.callback_query(F.data == "lead:back")
async def go_back(callback: CallbackQuery, state: FSMContext):
    """Handle back button press to go to the previous step."""
    await handle_back_navigation(callback, state)


@navigation_router.message(F.text.lower() == "back")
async def text_back(message: Message, state: FSMContext):
    """Handle 'back' text command to go to the previous step."""
    # Check if user is in a state where 'back' text should work
    current_fsm_state = await state.get_state()
    if current_fsm_state and current_fsm_state.startswith("LeadForm:"):
        await handle_back_navigation(message, state)
    else:
        # Optional: Reply if 'back' is typed outside the form
        # await message.answer("Nothing to go back from. Start with /lead.")
        pass
