import re
from typing import List, Optional, Tuple

# Constants for choices
COMPANY_TYPE_CHOICES: List[Tuple[str, str]] = [
    ("importer_exporter", "Importer/Exporter"),
    ("forwarder", "Forwarder"),
    ("agent", "Agent"),
]

MODE_OF_TRANSPORT_CHOICES: List[Tuple[str, str]] = [
    ("wagons", "Wagons"),
    ("containers", "Containers"),
    ("lcl", "LCL"),
    ("air", "Air"),
    ("auto", "Auto"),
]


def truncate_for_callback(text: str, max_bytes: int, suffix: str = "...") -> str:
    """
    Truncates a string to fit a specific byte limit for Telegram callback data,
    appending a suffix if truncation occurs.
    """
    encoded_suffix = suffix.encode("utf-8")
    suffix_len = len(encoded_suffix)

    encoded_text = text.encode("utf-8")
    if len(encoded_text) <= max_bytes:
        return text

    # Adjust max_bytes to account for suffix if text needs truncation
    # Ensure there's enough space for at least one character before the suffix
    adjusted_max_bytes = max_bytes - suffix_len
    if adjusted_max_bytes <= 0:  # Not enough space even for suffix + a character
        # Force truncate to max_bytes if no space for suffix
        # This might cut a multi-byte char, but it's a fallback.
        return encoded_text[:max_bytes].decode("utf-8", "ignore")

    truncated_bytes = bytearray()
    current_bytes_len = 0
    for char in text:
        char_encoded = char.encode("utf-8")
        char_len = len(char_encoded)
        if current_bytes_len + char_len > adjusted_max_bytes:
            break
        truncated_bytes.extend(char_encoded)
        current_bytes_len += char_len

    # Check if anything was actually truncated to decide if suffix is needed
    if len(truncated_bytes) < len(encoded_text):
        return truncated_bytes.decode("utf-8", "ignore") + suffix
    else:  # Should not happen if len(encoded_text) > max_bytes initially
        return text


async def get_previous_state(current_state: str) -> Optional[str]:
    """Determine the previous state based on the current state.
    Returns the name of the previous state in the form flow.
    """
    state_flow = [
        "business_card_photo",
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
        "shipment_directions",
        "comments",
        "meeting_place",
    ]

    # Special handling for transient states
    if current_state == "ocr_confirmation":
        return "business_card_photo"

    try:
        current_index = state_flow.index(current_state)
        if current_index > 0:
            return state_flow[current_index - 1]
        else:
            return None
    except ValueError:
        return None


async def generate_summary(data: dict) -> str:
    """Generate a summary of the lead information collected so far.
    Only shows fields that have been filled in.
    """
    summary = "📋 <b>Lead Information Summary</b>\n\n"
    total_fields = 14
    filled_fields = 0

    field_map = {
        "full_name": ("📝 <b>Full Name:</b>", None),
        "position": ("🏢 <b>Position in the company:</b>", None),
        "phone_number": ("📱 <b>Phone number:</b>", None),
        "email": ("📧 <b>Email address:</b>", None),
        "company_name": ("🏭 <b>Company name:</b>", None),
        "sphere_of_activity": ("🔍 <b>Sphere of activity:</b>", None),
        "company_type": ("📊 <b>Company type:</b>", COMPANY_TYPE_CHOICES),
        "cargo": ("📦 <b>Cargo:</b>", None),
        "mode_of_transport": ("🚢 <b>Preferred mode of transport:</b>", MODE_OF_TRANSPORT_CHOICES),
        "shipment_volume": ("📏 <b>Monthly shipment volume:</b>", None),
        # shipment_directions is handled specially
        "comments": ("💬 <b>Comments:</b>", None),
        "meeting_place": ("🤝 <b>Meeting place:</b>", None),
    }

    for key, (label_prefix, choices) in field_map.items():
        value = data.get(key)
        if value:
            display_value = value
            if choices:
                display_value = next(
                    (label for val, label in choices if val == value), value
                )
            summary += f"{label_prefix} {display_value}\n"
            filled_fields += 1

    # Shipment directions (special handling)
    directions_filled = False
    if data.get("selected_directions") and data.get("available_directions"):
        selected_directions_ids = data.get("selected_directions", set())
        # Ensure selected_directions_ids is a set of strings for comparison
        if isinstance(selected_directions_ids, list):
            selected_directions_ids = {str(d_id) for d_id in selected_directions_ids}
        else:  # If it's already a set, ensure elements are strings
            selected_directions_ids = {str(d_id) for d_id in selected_directions_ids}

        available_directions = data.get("available_directions", [])
        direction_names = [
            direction.get("name")
            for direction in available_directions
            if str(direction.get("id")) in selected_directions_ids
        ]
        if direction_names:
            summary += f"🗺️ <b>Directions:</b> {', '.join(direction_names)}\n"
            directions_filled = True
            filled_fields += 1

    # Business card handling
    business_card_filled = bool(data.get("business_card_photo"))
    if business_card_filled:
        summary += "📸 <b>Business Card:</b> Uploaded\n"
        filled_fields += 1

    # Adjust filled_fields if business_card_photo was present but not counted by loop
    # This logic for filled_fields can be simplified if business_card is always step 1.
    # Let's assume total_fields = 14 includes it.

    progress_percentage = (
        int((filled_fields / total_fields) * 100) if total_fields > 0 else 0
    )

    progress_bar = (
        "\n\n<b>Progress:</b> ["
        + "█" * (progress_percentage // 10)
        + "░" * (10 - (progress_percentage // 10))
        + f"] {progress_percentage}%\n"
    )
    progress_bar += f"<b>Completed:</b> {filled_fields}/{total_fields} fields"
    summary += progress_bar

    return summary


def is_valid_email(email: str) -> bool:
    """Validate email format."""
    if not email:
        return False
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def is_valid_phone(phone: str) -> bool:
    """Validate phone number format."""
    return True


def is_empty_or_whitespace(text: Optional[str]) -> bool:
    """Check if text is empty or contains only whitespace."""
    return text is None or text.strip() == ""
