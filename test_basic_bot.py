import asyncio
import os
import time

from environs import Env
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.custom.message import Message  # For type hinting

# --- Environment Setup ---
env = Env()
env.read_env(".env")  # Load .env file

TELETHON_API_ID = env.int("TELETHON_API_ID")
TELETHON_API_HASH = env.str("TELETHON_API_HASH")
TELETHON_PHONE = env.str("TELETHON_PHONE")
TEST_BOT_USERNAME = env.str("TEST_BOT_USERNAME")

# --- Global State for Test ---
# Stores the last message ID received from the bot in a chat to avoid reprocessing old messages.
# Key: chat_id (int), Value: message_id (int)
_last_message_ids = {}


# --- Helper Functions ---
async def get_bot_response(
    client: TelegramClient,
    chat_entity_or_username,  # Can be username string or chat entity
    timeout: int = 15,  # Increased timeout for potentially slow bot responses or edits
    expect_edit_of_msg_id: int = None,
    original_text_if_edit: str = None,  # Optional: to ensure text actually changed
) -> Message:
    """
    Waits for and returns the next message from the bot in the specified chat.
    Can also wait for a specific message to be edited.
    """
    chat_entity = await client.get_entity(chat_entity_or_username)

    start_time = time.monotonic()
    # Use the specific chat_entity.id for _last_message_ids key
    last_seen_id_for_chat = _last_message_ids.get(chat_entity.id, 0)

    while time.monotonic() - start_time < timeout:
        if expect_edit_of_msg_id:
            try:
                msg = await client.get_messages(chat_entity, ids=expect_edit_of_msg_id)
                if msg and msg.edit_date:
                    if (
                        original_text_if_edit
                        and msg.text == original_text_if_edit
                        and msg.buttons is None
                        and (
                            await client.get_messages(
                                chat_entity, ids=expect_edit_of_msg_id
                            )
                        ).buttons
                        is None
                    ):
                        # If text is same and buttons are also same (or both None), it might not be the edit we want.
                        # This check is a bit basic, might need refinement if edits are very subtle.
                        pass
                    else:
                        # _last_message_ids[chat_entity.id] = msg.id # Update last seen ID to this edited message
                        return msg
            except Exception:
                # Message might not be found if deleted, or other errors
                pass  # Fall through to check for new messages

        # Check for new messages from the bot
        # from_user=chat_entity ensures we only get messages sent by the bot itself
        messages = await client.get_messages(
            chat_entity, limit=10, from_user=chat_entity
        )

        # Filter for messages newer than the last seen one in this specific chat
        new_messages = [m for m in messages if m.id > last_seen_id_for_chat]

        # Exclude the message we are expecting an edit from, if applicable
        if expect_edit_of_msg_id:
            new_messages = [m for m in new_messages if m.id != expect_edit_of_msg_id]

        if new_messages:
            latest_message = max(new_messages, key=lambda m: m.id)
            _last_message_ids[chat_entity.id] = latest_message.id
            return latest_message

        await asyncio.sleep(0.5)  # Polling interval

    raise TimeoutError(
        f"Timeout: No new message or expected edit from bot {chat_entity_or_username} within {timeout}s. Last seen ID for chat: {last_seen_id_for_chat}"
    )


async def find_button_by_text(message: Message, text: str, exact: bool = False):
    """Finds an inline button by its text (partial match by default)."""
    if not message.buttons:
        return None
    for row in message.buttons:
        for button in row:
            if exact:
                if button.text == text:
                    return button
            else:
                if text in button.text:
                    return button
    return None


# --- Test Logic ---
async def test_lead_form_happy_path(client: TelegramClient, bot_username: str):
    bot_entity = await client.get_entity(bot_username)
    _last_message_ids.pop(bot_entity.id, None)  # Reset for a clean run

    current_msg = None  # To keep track of the message object

    async def check_and_print_step(
        expected_text_part: str,
        step_name: str,
        is_edit: bool = False,
        prev_msg_id_for_edit: int = None,
        action_description: str = None,
    ):
        nonlocal current_msg
        print(
            f"\n--- {step_name} ({action_description or ('Fetching new' if not is_edit else 'Fetching edit')}) ---"
        )

        original_text_for_edit_check = (
            current_msg.text if is_edit and current_msg else None
        )

        if is_edit:
            assert prev_msg_id_for_edit is not None, (
                "prev_msg_id_for_edit required for edit check"
            )
            current_msg = await get_bot_response(
                client,
                bot_username,
                expect_edit_of_msg_id=prev_msg_id_for_edit,
                original_text_if_edit=original_text_for_edit_check,
            )
        else:
            current_msg = await get_bot_response(client, bot_username)

        # Normalize line breaks for printing and assertion
        msg_text_oneline = current_msg.text.replace("\n", " ").replace("\r", "")
        print(f"Bot: {msg_text_oneline[:180]}...")
        if current_msg.buttons:
            button_texts = [[b.text for b in row] for row in current_msg.buttons]
            print(f"Buttons: {button_texts}")

        assert expected_text_part in current_msg.text, (
            f"AssertionError in {step_name}: Expected '{expected_text_part}' not in bot's message. Got: '{current_msg.text}'"
        )
        return current_msg  # Return the fetched/updated message object

    # Step 1: /lead -> Exhibition Selection
    await client.send_message(bot_username, "/lead")
    current_msg = await check_and_print_step(
        "Step 1/15: Please select the exhibition",
        "Exhibition Selection",
        action_description="Sent /lead",
    )
    assert current_msg.buttons and len(current_msg.buttons[0]) > 0, (
        "Exhibition buttons missing"
    )

    # Step 2: Select Exhibition -> Business Card Prompt
    exhibition_button = current_msg.buttons[0][0]  # Click the first exhibition
    prev_msg_id = current_msg.id
    await exhibition_button.click()
    current_msg = await check_and_print_step(
        "Step 2/15: Upload a business card photo",
        "Business Card Prompt",
        is_edit=True,
        prev_msg_id_for_edit=prev_msg_id,
        action_description=f"Clicked '{exhibition_button.text}'",
    )
    skip_bc_button = await find_button_by_text(current_msg, "Skip Business Card")
    assert skip_bc_button, "Skip Business Card button not found"

    # Step 3: Skip Business Card -> Manual Filling Confirmation & Full Name Prompt
    prev_msg_id = current_msg.id
    await skip_bc_button.click()
    # First, original message is edited (buttons removed)
    await check_and_print_step(
        current_msg.text,
        "Business Card Prompt (Buttons Removed)",
        is_edit=True,
        prev_msg_id_for_edit=prev_msg_id,
        action_description=f"Clicked '{skip_bc_button.text}' - verifying edit",
    )
    assert current_msg.buttons is None or len(current_msg.buttons) == 0, (
        "Buttons not removed after skipping BC"
    )
    # Next, "Manual form filling selected." message
    current_msg = await check_and_print_step(
        "Manual form filling selected.",
        "Skip BC Confirmation",
        action_description="Skipped BC - new message",
    )
    # Finally, "Full Name" prompt
    current_msg = await check_and_print_step(
        "Step 3/15: What is your name?",
        "Full Name Prompt",
        action_description="Skipped BC - next prompt",
    )
    assert await find_button_by_text(current_msg, "Back"), "Back button missing"

    # Step 4: Full Name -> Position Prompt
    await client.send_message(bot_username, "Test User Alpha")
    current_msg = await check_and_print_step(
        "Step 3/14: What is the position",
        "Position Prompt",
        action_description="Sent Full Name",
    )

    # Step 5: Position -> Phone Prompt
    await client.send_message(bot_username, "Lead Tester")
    current_msg = await check_and_print_step(
        "Step 4/14: What is the phone number",
        "Phone Prompt",
        action_description="Sent Position",
    )

    # Step 6: Phone -> Email Prompt
    await client.send_message(bot_username, "+12223334455")
    current_msg = await check_and_print_step(
        "Step 5/14: What is the email address",
        "Email Prompt",
        action_description="Sent Phone",
    )
    assert await find_button_by_text(current_msg, "Skip Email"), (
        "Skip Email button missing"
    )

    # Step 7: Email -> Company Name Prompt
    await client.send_message(bot_username, "test.lead@example.com")
    current_msg = await check_and_print_step(
        "Step 6/14: What is the company name",
        "Company Name Prompt",
        action_description="Sent Email",
    )

    # Step 8: Company Name -> Sphere of Activity Prompt
    await client.send_message(bot_username, "Telethon Test Corp")
    current_msg = await check_and_print_step(
        "Step 7/14: What is the company's sphere of activity",
        "Sphere of Activity Prompt",
        action_description="Sent Company Name",
    )

    # Step 9: Sphere of Activity -> Company Type Prompt
    await client.send_message(bot_username, "Automated Testing Solutions")
    current_msg = await check_and_print_step(
        "Step 8/14: What is the company type",
        "Company Type Prompt",
        action_description="Sent Sphere",
    )
    assert current_msg.buttons, "Company type buttons missing"

    # Step 10: Company Type -> Cargo Prompt
    company_type_button = current_msg.buttons[0][0]  # Click first option
    prev_msg_id = current_msg.id
    await company_type_button.click()
    current_msg = await check_and_print_step(
        "Step 9/14: What type of cargo",
        "Cargo Prompt",
        is_edit=True,
        prev_msg_id_for_edit=prev_msg_id,
        action_description=f"Clicked '{company_type_button.text}'",
    )

    # Step 11: Cargo -> Mode of Transport Prompt
    await client.send_message(bot_username, "Test Data Packages")
    current_msg = await check_and_print_step(
        "Step 10/14: What is the preferred mode of transport",
        "Mode of Transport Prompt",
        action_description="Sent Cargo",
    )
    assert current_msg.buttons, "Mode of transport buttons missing"

    # Step 12: Mode of Transport -> Shipment Volume Prompt
    transport_mode_button = current_msg.buttons[0][0]  # Click first option
    prev_msg_id = current_msg.id
    await transport_mode_button.click()
    current_msg = await check_and_print_step(
        "Step 11/14: What is the monthly shipment volume",
        "Shipment Volume Prompt",
        is_edit=True,
        prev_msg_id_for_edit=prev_msg_id,
        action_description=f"Clicked '{transport_mode_button.text}'",
    )

    # Step 13: Shipment Volume -> Shipment Directions Prompt
    await client.send_message(bot_username, "Approx 100 TB")
    # This step in the bot sends a new message after fetching directions.
    current_msg = await check_and_print_step(
        "Step 12/14: Please select the shipment directions",
        "Shipment Directions Prompt",
        action_description="Sent Shipment Volume",
    )
    assert current_msg.buttons and await find_button_by_text(current_msg, "Done"), (
        "Shipment direction/Done buttons missing"
    )

    # Step 14: Shipment Directions -> Comments Prompt
    direction_button_to_click = current_msg.buttons[0][0]  # Click first direction
    direction_text_original = direction_button_to_click.text
    prev_msg_id = current_msg.id
    await direction_button_to_click.click()
    current_msg = await check_and_print_step(
        f"{direction_text_original}</b> added",
        "Direction Selected",
        is_edit=True,
        prev_msg_id_for_edit=prev_msg_id,
        action_description=f"Clicked direction '{direction_text_original}'",
    )
    # Verify button is marked
    marked_button = await find_button_by_text(current_msg, direction_text_original)
    assert marked_button and marked_button.text.startswith("☑️"), (
        f"Button '{direction_text_original}' not marked"
    )

    done_directions_button = await find_button_by_text(current_msg, "Done")
    assert done_directions_button, "Done button for directions not found"
    prev_msg_id = current_msg.id
    await done_directions_button.click()
    current_msg = await check_and_print_step(
        "Step 13/14: Do you have any additional comments",
        "Comments Prompt",
        is_edit=True,
        prev_msg_id_for_edit=prev_msg_id,
        action_description="Clicked 'Done' for directions",
    )

    # Step 15: Comments -> Meeting Place Prompt
    await client.send_message(bot_username, "All systems nominal.")
    current_msg = await check_and_print_step(
        "Step 14/15: Where did the meeting take place",
        "Meeting Place Prompt",
        action_description="Sent Comments",
    )
    assert current_msg.buttons, "Meeting place buttons missing"

    # Step 16: Meeting Place -> Importance Prompt
    meeting_place_btn = await find_button_by_text(current_msg, "Our Booth")
    assert meeting_place_btn, "'Our Booth' button not found"
    prev_msg_id = current_msg.id
    await meeting_place_btn.click()
    current_msg = await check_and_print_step(
        "Step 15/16: How would you rate the importance",
        "Importance Prompt",
        is_edit=True,
        prev_msg_id_for_edit=prev_msg_id,
        action_description=f"Clicked '{meeting_place_btn.text}'",
    )
    assert current_msg.buttons, "Importance buttons missing"

    # Step 17: Importance -> Final Summary
    importance_btn = await find_button_by_text(current_msg, "Medium")
    assert importance_btn, "'Medium' importance button not found"
    prev_msg_id = current_msg.id
    await importance_btn.click()
    current_msg = await check_and_print_step(
        "Lead Information Complete",
        "Final Summary",
        is_edit=True,
        prev_msg_id_for_edit=prev_msg_id,
        action_description=f"Clicked '{importance_btn.text}'",
    )
    confirm_lead_btn = await find_button_by_text(current_msg, "Confirm")
    assert confirm_lead_btn, "Confirm button on final summary not found"

    # Step 18: Confirm Lead -> Processing & Success
    prev_msg_id = current_msg.id
    original_text_before_confirm = current_msg.text
    await confirm_lead_btn.click()
    # First edit to "Processing..."
    current_msg = await check_and_print_step(
        "Processing...",
        "Confirmation Processing",
        is_edit=True,
        prev_msg_id_for_edit=prev_msg_id,
        action_description="Clicked 'Confirm Lead'",
    )

    # Second edit to "Success!"
    prev_msg_id_for_success = current_msg.id  # ID of the "Processing..." message
    original_text_processing = current_msg.text
    current_msg = await check_and_print_step(
        "Success!",
        "Confirmation Success",
        is_edit=True,
        prev_msg_id_for_edit=prev_msg_id_for_success,
        action_description="Waiting for final success",
    )

    print("\n✅✅✅ Lead form happy path test completed successfully! ✅✅✅")


# --- Main Execution ---
async def main():
    client = TelegramClient("test_user_session", TELETHON_API_ID, TELETHON_API_HASH)
    try:
        print("Connecting to Telegram...")
        await client.connect()
        if not await client.is_user_authorized():
            print("First run: Authorizing user...")
            await client.send_code_request(TELETHON_PHONE)
            code = input("Enter the Telegram code you received: ")
            try:
                await client.sign_in(TELETHON_PHONE, code)
            except SessionPasswordNeededError:
                password = input("Your Telegram two-factor authentication password: ")
                await client.sign_in(password=password)

        print("User authorized successfully.")

        # Optional: Send /start to bot to ensure it's responsive
        print(f"Pinging @{TEST_BOT_USERNAME} with /start...")
        bot_entity_for_ping = await client.get_entity(TEST_BOT_USERNAME)
        _last_message_ids.pop(
            bot_entity_for_ping.id, None
        )  # Clear last ID for this bot
        await client.send_message(TEST_BOT_USERNAME, "/start")
        try:
            start_reply = await get_bot_response(client, TEST_BOT_USERNAME, timeout=5)
            print(
                f"@{TEST_BOT_USERNAME} replied to /start: {start_reply.text[:60].replace(os.linesep, ' ')}..."
            )
        except TimeoutError:
            print(
                f"Warning: @{TEST_BOT_USERNAME} did not reply to /start. Test will proceed but bot might be unresponsive."
            )

        # Run the main test
        await test_lead_form_happy_path(client, TEST_BOT_USERNAME)

    except Exception as e:
        print(f"\n❌❌❌ An error occurred during the test: {e} ❌❌❌")
        import traceback

        traceback.print_exc()
    finally:
        print("Disconnecting client...")
        if client.is_connected():
            await client.disconnect()
        print("Client disconnected.")


if __name__ == "__main__":
    asyncio.run(main())
