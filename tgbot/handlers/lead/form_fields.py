"""
Form field handlers for processing user input for each field in the lead form.
"""

from aiogram import F, Router
from aiogram.filters import StateFilter
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

from .business_card import show_summary  # Relative import
from .core import (  # Relative import
    COMPANY_TYPE_CHOICES,
    MODE_OF_TRANSPORT_CHOICES,
    generate_summary,
    is_empty_or_whitespace,
    is_valid_email,
    is_valid_phone,
    truncate_for_callback,  # Import the new utility
)

form_fields_router = Router()

# Define callback data limits from navigation.py or centrally
SUGGESTION_VALUE_MAX_BYTES = {
    "name": 38,
    "position": 30,
    "phone": 35,
    "email": 35,
    "company": 30,
}


async def _fetch_and_set_shipment_directions(message: Message, state: FSMContext):
    """Helper to fetch directions and set up the next step or error."""
    data = await state.get_data()
    summary = await generate_summary(data)
    config = load_config()

    async with MyApi(config=config) as api:
        status, response = await api.get_shipment_directions()

    if status != 200 or not response:
        retry_keyboard = [
            [
                InlineKeyboardButton(
                    text="🔄 Try Again", callback_data="retry_fetch_directions"
                )
            ],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="lead:back")],
        ]
        retry_markup = InlineKeyboardMarkup(inline_keyboard=retry_keyboard)
        await message.answer(
            f"{summary}\n\n❌ Unable to fetch shipment directions. Please try again later or go back.",
            parse_mode="HTML",
            reply_markup=retry_markup,
        )
        # Stay in LeadForm.shipment_volume state for retry
        return False

    directions_data = (
        response.get("results") if isinstance(response, dict) else response
    )
    if not isinstance(directions_data, list) or not directions_data:
        await message.answer(
            f"{summary}\n\n❌ No shipment directions available. Please try again later.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Back", callback_data="lead:back")]
                ]
            ),
        )
        return False  # Stay in current state or allow back

    await state.update_data(
        available_directions=directions_data, selected_directions=set()
    )

    keyboard_rows = []
    for direction in directions_data:
        dir_id = direction.get("id")
        dir_name = direction.get("name")
        if dir_id and dir_name:
            keyboard_rows.append(
                [
                    InlineKeyboardButton(
                        text=dir_name, callback_data=f"direction:{dir_id}"
                    )
                ]
            )

    keyboard_rows.append(
        [InlineKeyboardButton(text="✅ Done", callback_data="directions:done")]
    )
    keyboard_rows.append(
        [InlineKeyboardButton(text="⬅️ Back", callback_data="lead:back")]
    )
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await message.answer(
        f"{summary}\n\n<b>Step 12/14:</b> Please select the shipment directions (you can select multiple):",
        parse_mode="HTML",
        reply_markup=markup,
    )
    await state.set_state(LeadForm.shipment_directions)
    return True


@form_fields_router.message(StateFilter(LeadForm.full_name))
async def process_full_name(message: Message, state: FSMContext):
    if is_empty_or_whitespace(message.text):
        await message.answer(
            "❌ <b>Error:</b> Name cannot be empty. Please enter your full name.",
            parse_mode="HTML",
        )
        return
    await state.update_data(full_name=message.text)
    data = await state.get_data()
    summary = await generate_summary(data)
    extracted_data = data.get("extracted_data", {})
    keyboard_rows = []
    if data.get("ocr_processed") and extracted_data.get("position"):
        val = extracted_data.get("position")
        safe_val = truncate_for_callback(val, SUGGESTION_VALUE_MAX_BYTES["position"])
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text=f"Use: {val}",
                    callback_data=f"use_suggestion:position:{safe_val}",
                )
            ]
        )
    keyboard_rows.append(
        [InlineKeyboardButton(text="⬅️ Back", callback_data="lead:back")]
    )
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    await message.answer(
        f"{summary}\n\n<b>Step 3/14:</b> What is the position in the company?",
        parse_mode="HTML",
        reply_markup=markup,
    )
    await state.set_state(LeadForm.position)


@form_fields_router.message(StateFilter(LeadForm.position))
async def process_position(message: Message, state: FSMContext):
    if is_empty_or_whitespace(message.text):  # Added validation
        await message.answer(
            "❌ <b>Error:</b> Position cannot be empty.", parse_mode="HTML"
        )
        return
    await state.update_data(position=message.text)
    data = await state.get_data()
    summary = await generate_summary(data)
    extracted_data = data.get("extracted_data", {})
    keyboard_rows = []
    phone_val = extracted_data.get("phone") or extracted_data.get("phone_number")
    if data.get("ocr_processed") and phone_val:
        safe_val = truncate_for_callback(phone_val, SUGGESTION_VALUE_MAX_BYTES["phone"])
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text=f"Use: {phone_val}",
                    callback_data=f"use_suggestion:phone:{safe_val}",
                )
            ]
        )
    keyboard_rows.append(
        [InlineKeyboardButton(text="⬅️ Back", callback_data="lead:back")]
    )
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    await message.answer(
        f"{summary}\n\n<b>Step 4/14:</b> What is the phone number?",
        parse_mode="HTML",
        reply_markup=markup,
    )
    await state.set_state(LeadForm.phone_number)


@form_fields_router.message(StateFilter(LeadForm.phone_number))
async def process_phone_number(message: Message, state: FSMContext):
    if is_empty_or_whitespace(message.text):
        await message.answer(
            "❌ <b>Error:</b> Phone number cannot be empty.", parse_mode="HTML"
        )
        return
    if not is_valid_phone(message.text):
        await message.answer(
            "❌ <b>Error:</b> Invalid phone number format.", parse_mode="HTML"
        )
        return
    await state.update_data(phone_number=message.text)
    data = await state.get_data()
    summary = await generate_summary(data)
    extracted_data = data.get("extracted_data", {})
    keyboard_rows = []
    if data.get("ocr_processed") and extracted_data.get("email"):
        val = extracted_data.get("email")
        safe_val = truncate_for_callback(val, SUGGESTION_VALUE_MAX_BYTES["email"])
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text=f"Use: {val}", callback_data=f"use_suggestion:email:{safe_val}"
                )
            ]
        )
    keyboard_rows.append(
        [InlineKeyboardButton(text="⬅️ Back", callback_data="lead:back")]
    )
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    await message.answer(
        f"{summary}\n\n<b>Step 5/14:</b> What is the email address?",
        parse_mode="HTML",
        reply_markup=markup,
    )
    await state.set_state(LeadForm.email)


@form_fields_router.message(StateFilter(LeadForm.email))
async def process_email(message: Message, state: FSMContext):
    if is_empty_or_whitespace(message.text):
        await message.answer(
            "❌ <b>Error:</b> Email cannot be empty.", parse_mode="HTML"
        )
        return
    if not is_valid_email(message.text):
        await message.answer(
            "❌ <b>Error:</b> Invalid email format.", parse_mode="HTML"
        )
        return
    await state.update_data(email=message.text)
    data = await state.get_data()
    summary = await generate_summary(data)
    extracted_data = data.get("extracted_data", {})
    keyboard_rows = []
    if data.get("ocr_processed") and extracted_data.get("company_name"):
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
    keyboard_rows.append(
        [InlineKeyboardButton(text="⬅️ Back", callback_data="lead:back")]
    )
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    await message.answer(
        f"{summary}\n\n<b>Step 6/14:</b> What is the company name?",
        parse_mode="HTML",
        reply_markup=markup,
    )
    await state.set_state(LeadForm.company_name)


@form_fields_router.message(StateFilter(LeadForm.company_name))
async def process_company_name(message: Message, state: FSMContext):
    if is_empty_or_whitespace(message.text):
        await message.answer(
            "❌ <b>Error:</b> Company name cannot be empty.", parse_mode="HTML"
        )
        return
    await state.update_data(company_name=message.text)
    data = await state.get_data()
    summary = await generate_summary(data)
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="lead:back")]
        ]
    )
    await message.answer(
        f"{summary}\n\n<b>Step 7/14:</b> What is the company's sphere of activity?",
        parse_mode="HTML",
        reply_markup=markup,
    )
    await state.set_state(LeadForm.sphere_of_activity)


@form_fields_router.message(StateFilter(LeadForm.sphere_of_activity))
async def process_sphere_of_activity(message: Message, state: FSMContext):
    if is_empty_or_whitespace(message.text):  # Added validation
        await message.answer(
            "❌ <b>Error:</b> Sphere of activity cannot be empty.", parse_mode="HTML"
        )
        return
    await state.update_data(sphere_of_activity=message.text)
    data = await state.get_data()
    summary = await generate_summary(data)
    keyboard_rows = []
    for value, label in COMPANY_TYPE_CHOICES:
        keyboard_rows.append(
            [InlineKeyboardButton(text=label, callback_data=f"company_type:{value}")]
        )
    keyboard_rows.append(
        [InlineKeyboardButton(text="⬅️ Back", callback_data="lead:back")]
    )
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    await message.answer(
        f"{summary}\n\n<b>Step 8/14:</b> What is the company type?",
        parse_mode="HTML",
        reply_markup=markup,
    )
    await state.set_state(LeadForm.company_type)


@form_fields_router.callback_query(
    LeadForm.company_type, F.data.startswith("company_type:")
)
async def process_company_type(callback: CallbackQuery, state: FSMContext):
    company_type_val = callback.data.split(":")[1]
    await state.update_data(company_type=company_type_val)
    data = await state.get_data()
    summary = await generate_summary(data)
    company_type_label = next(
        (label for value, label in COMPANY_TYPE_CHOICES if value == company_type_val),
        company_type_val,
    )

    next_step_markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="lead:back")]
        ]
    )

    await callback.message.edit_text(
        f"Selected company type: <b>{company_type_label}</b>\n\n{summary}\n\n<b>Step 9/14:</b> What type of cargo do you handle?",
        parse_mode="HTML",
        reply_markup=next_step_markup,
    )
    await state.set_state(LeadForm.cargo)
    await callback.answer()


@form_fields_router.message(StateFilter(LeadForm.cargo))
async def process_cargo(message: Message, state: FSMContext):
    if is_empty_or_whitespace(message.text):
        await message.answer(
            "❌ <b>Error:</b> Cargo information cannot be empty.", parse_mode="HTML"
        )
        return
    await state.update_data(cargo=message.text)
    data = await state.get_data()
    summary = await generate_summary(data)
    keyboard_rows = []
    for value, label in MODE_OF_TRANSPORT_CHOICES:
        keyboard_rows.append(
            [InlineKeyboardButton(text=label, callback_data=f"transport:{value}")]
        )
    keyboard_rows.append(
        [InlineKeyboardButton(text="⬅️ Back", callback_data="lead:back")]
    )
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    await message.answer(
        f"{summary}\n\n<b>Step 10/14:</b> What is the preferred mode of transport?",
        parse_mode="HTML",
        reply_markup=markup,
    )
    await state.set_state(LeadForm.mode_of_transport)


@form_fields_router.callback_query(
    LeadForm.mode_of_transport, F.data.startswith("transport:")
)
async def process_mode_of_transport(callback: CallbackQuery, state: FSMContext):
    mode_val = callback.data.split(":")[1]
    await state.update_data(mode_of_transport=mode_val)
    data = await state.get_data()
    summary = await generate_summary(data)
    mode_label = next(
        (label for value, label in MODE_OF_TRANSPORT_CHOICES if value == mode_val),
        mode_val,
    )

    next_step_markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="lead:back")]
        ]
    )

    await callback.message.edit_text(
        f"Selected transport mode: <b>{mode_label}</b>\n\n{summary}\n\n<b>Step 11/14:</b> What is your monthly shipment volume?",
        parse_mode="HTML",
        reply_markup=next_step_markup,
    )
    await state.set_state(LeadForm.shipment_volume)
    await callback.answer()


@form_fields_router.message(StateFilter(LeadForm.shipment_volume))
async def process_shipment_volume(message: Message, state: FSMContext):
    if is_empty_or_whitespace(message.text):
        await message.answer(
            "❌ <b>Error:</b> Shipment volume cannot be empty.", parse_mode="HTML"
        )
        return
    await state.update_data(shipment_volume=message.text)
    await _fetch_and_set_shipment_directions(message, state)


@form_fields_router.callback_query(
    LeadForm.shipment_volume, F.data == "retry_fetch_directions"
)
async def retry_fetch_shipment_directions_cb(
    callback: CallbackQuery, state: FSMContext
):
    await callback.answer("Retrying to fetch shipment directions...")
    # Edit the "retry" message to indicate processing, then call the helper
    try:
        await callback.message.edit_text(
            f"{await generate_summary(await state.get_data())}\n\n⏳ Retrying to fetch shipment directions...",
            parse_mode="HTML",
            reply_markup=None,
        )
    except Exception:  # If edit fails, proceed anyway
        pass
    await _fetch_and_set_shipment_directions(callback.message, state)


@form_fields_router.callback_query(
    LeadForm.shipment_directions, F.data.startswith("direction:")
)
async def process_direction_selection(callback: CallbackQuery, state: FSMContext):
    direction_id_selected = callback.data.split(":")[1]
    data = await state.get_data()
    current_selected_ids = data.get("selected_directions", set())
    if isinstance(current_selected_ids, list):  # Ensure it's a set
        current_selected_ids = set(current_selected_ids)

    if direction_id_selected in current_selected_ids:
        current_selected_ids.remove(direction_id_selected)
        action_text = "removed from"
    else:
        current_selected_ids.add(direction_id_selected)
        action_text = "added to"

    await state.update_data(
        selected_directions=list(current_selected_ids)
    )  # Store as list for JSON

    updated_data = await state.get_data()  # Get data again after update
    summary = await generate_summary(updated_data)
    available_directions = updated_data.get("available_directions", [])

    keyboard_rows = []
    selected_direction_name = f"Direction {direction_id_selected}"  # Fallback name
    for direction in available_directions:
        dir_id_str = str(direction.get("id"))
        dir_name = direction.get("name")
        if dir_id_str and dir_name:
            if dir_id_str == direction_id_selected:
                selected_direction_name = dir_name
            prefix = "✅ " if dir_id_str in current_selected_ids else ""
            keyboard_rows.append(
                [
                    InlineKeyboardButton(
                        text=f"{prefix}{dir_name}",
                        callback_data=f"direction:{dir_id_str}",
                    )
                ]
            )

    keyboard_rows.append(
        [InlineKeyboardButton(text="✅ Done", callback_data="directions:done")]
    )
    keyboard_rows.append(
        [InlineKeyboardButton(text="⬅️ Back", callback_data="lead:back")]
    )
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    status_message = (
        f"<b>{selected_direction_name}</b> {action_text} your selected directions."
    )
    await callback.message.edit_text(
        f"{status_message}\n\n{summary}\n\n<b>Step 12/14:</b> Please select the shipment directions (you can select multiple):",
        parse_mode="HTML",
        reply_markup=markup,
    )
    await callback.answer()


@form_fields_router.callback_query(
    LeadForm.shipment_directions, F.data == "directions:done"
)
async def process_directions_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_ids = data.get("selected_directions", set())
    if not selected_ids:
        await callback.answer(
            "Please select at least one shipment direction.", show_alert=True
        )
        return

    summary = await generate_summary(data)
    available_directions = data.get("available_directions", [])
    selected_names = [
        direction.get("name")
        for direction in available_directions
        if str(direction.get("id"))
        in selected_ids  # selected_ids is now a set of strings
    ]

    next_step_markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="lead:back")]
        ]
    )

    # Edit the current message
    await callback.message.edit_text(
        f"Selected directions: <b>{', '.join(selected_names)}</b>\n\n{summary}\n\n<b>Step 13/14:</b> Do you have any additional comments? (Type 'none' if you don't have any)",
        parse_mode="HTML",
        reply_markup=next_step_markup,  # Keyboard for the next step
    )
    await state.set_state(LeadForm.comments)
    await callback.answer()


@form_fields_router.message(StateFilter(LeadForm.comments))
async def process_comments(message: Message, state: FSMContext):
    comment_text = (
        None if message.text and message.text.lower() == "none" else message.text
    )
    await state.update_data(comments=comment_text)
    data = await state.get_data()
    summary = await generate_summary(data)
    confirmation_msg = (
        f"Comments saved: <b>{comment_text}</b>"
        if comment_text
        else "No comments added."
    )

    keyboard_rows = [
        [
            InlineKeyboardButton(
                text="Our Booth", callback_data="meeting_place:our_booth"
            )
        ],
        [
            InlineKeyboardButton(
                text="Partner Booth", callback_data="meeting_place:partner_booth"
            )
        ],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="lead:back")],
    ]
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await message.answer(
        f"{confirmation_msg}\n\n{summary}\n\n<b>Step 14/14:</b> Where did the meeting take place?",
        parse_mode="HTML",
        reply_markup=markup,
    )
    await state.set_state(LeadForm.meeting_place)


@form_fields_router.callback_query(
    LeadForm.meeting_place, F.data.startswith("meeting_place:")
)
async def process_meeting_place(callback: CallbackQuery, state: FSMContext):
    meeting_place_val = callback.data.split(":")[1]
    meeting_place_label = (
        "Our Booth" if meeting_place_val == "our_booth" else "Partner Booth"
    )
    await state.update_data(meeting_place=meeting_place_label)
    data = await state.get_data()

    if data.get("business_card_photo") or data.get("business_card_skipped"):
        # Show summary in the same message
        summary_text = await generate_summary(await state.get_data())
        final_text = f"{summary_text}\n\n<b>✅ Lead Information Complete</b>\n\nPlease review the information above and confirm if it's correct."

        keyboard_rows = [
            [InlineKeyboardButton(text="✅ Confirm", callback_data="lead:confirm")],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="lead:cancel")],
            [InlineKeyboardButton(text="🔄 Restart", callback_data="lead:restart")],
        ]
        markup = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

        await callback.message.edit_text(
            f"Meeting place saved: <b>{meeting_place_label}</b>\n\n{final_text}",
            parse_mode="HTML",
            reply_markup=markup,
        )
    else:
        # Handle case where business card is not skipped
        keyboard_rows = [
            [
                InlineKeyboardButton(
                    text="Skip Business Card", callback_data="business_card:skip"
                )
            ]
        ]
        markup = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

        await callback.message.edit_text(
            f"Meeting place saved: <b>{meeting_place_label}</b>\n\n"
            "<b>Final Step: Business Card</b>\n\n"
            "Please upload a photo of your business card or use the button below to skip this step.",
            parse_mode="HTML",
            reply_markup=markup,
        )
        await state.set_state(LeadForm.business_card_photo)

    await callback.answer()
