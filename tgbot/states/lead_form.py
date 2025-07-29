from aiogram.fsm.state import State, StatesGroup


class LeadForm(StatesGroup):
    """States for the lead form collection process."""

    # Exhibition selection
    exhibition_selection = State()

    # Start with business card for OCR
    business_card_photo = State()
    ocr_confirmation = State()
    # Personal information
    full_name = State()
    position = State()
    phone_number = State()
    email = State()

    # Company information
    company_name = State()
    company_address = State()
    sphere_of_activity = State()
    company_type = State()

    # Cargo information
    cargo = State()
    mode_of_transport = State()
    shipment_volume = State()

    # Shipment directions
    shipment_directions = State()

    # Optional
    comments = State()

    # Meeting information
    meeting_place = State()

    # Lead importance
    importance = State()
