from infrastructure.some_api.base import BaseClient
from tgbot.config import Config


class MyApi(BaseClient):
    def __init__(self, config: Config, **kwargs):
        self.api_key = config.tg_bot.token
        self.base_url = "https://exhibition-api.interrail.uz"
        super().__init__(base_url=self.base_url)

    async def __aenter__(self):
        """Support for async with statement."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Ensure session is closed when exiting context."""
        await self.close()

    async def register(self, telegram_id: int, company_id: int, *args, **kwargs):
        headers = {"X-Telegram-Bot-API-Token": self.api_key}
        status, result = await self._make_request(
            method="POST",
            url="/api/accounts/telegram-registration/",
            headers=headers,
            json={"telegram_id": telegram_id, "company_id": company_id},
            *args,
            **kwargs,
        )
        return status, result

    async def login(self, telegram_id: int, *args, **kwargs):
        headers = {"X-Telegram-Bot-API-Token": self.api_key}
        status, result = await self._make_request(
            method="POST",
            url="/api/accounts/telegram-login/",
            headers=headers,
            json={"telegram_id": telegram_id},
            *args,
            **kwargs,
        )
        return status, result

    async def get_companies(self, *args, **kwargs):
        headers = {"X-Telegram-Bot-API-Token": self.api_key}
        status, result = await self._make_request(
            method="GET",
            url="/api/companies/list_via_telegram/",
            headers=headers,
            *args,
            **kwargs,
        )
        return status, result

    async def get_shipment_directions(self, *args, **kwargs):
        headers = {"X-Telegram-Bot-API-Token": self.api_key}
        status, result = await self._make_request(
            method="GET",
            url="/api/leads/shipment-directions/list_via_telegram/",
            headers=headers,
            *args,
            **kwargs,
        )
        return status, result

    async def get_exhibitions(self, *args, **kwargs):
        headers = {"X-Telegram-Bot-API-Token": self.api_key}
        status, result = await self._make_request(
            method="GET",
            url="/api/leads/categories/list_via_telegram/?is_active=true",
            headers=headers,
            *args,
            **kwargs,
        )
        return status, result

    async def create_lead(
        self, data: dict, business_card_photo_data=None, *args, **kwargs
    ):
        """Create a lead with optional business card photo.

        Args:
            data: Dictionary containing lead data
            business_card_photo_data: Optional file data for business card photo

        Returns:
            Tuple of (status_code, response_data)
        """
        headers = {"X-Telegram-Bot-API-Token": self.api_key}

        if business_card_photo_data:
            # If we have a photo, use multipart form data
            from aiohttp import FormData

            # Create form data with all lead fields
            form = FormData()

            # Add all text fields from data dictionary
            for key, value in data.items():
                # Handle lists (like shipment_directions) by adding multiple fields with same name
                if isinstance(value, list):
                    for item in value:
                        form.add_field(key, str(item))
                else:
                    form.add_field(key, str(value) if value is not None else "")

            # Add the business card photo
            form.add_field(
                "business_card_photo",
                business_card_photo_data,
                filename="business_card.jpg",
                content_type="image/jpeg",
            )

            # Make the request with form data
            status, result = await self._make_request(
                method="POST",
                url="/api/leads/lead-create-via-telegram/",
                headers=headers,
                data=form,  # Use form data instead of JSON
                *args,
                **kwargs,
            )
        else:
            # If no photo, use regular JSON request
            status, result = await self._make_request(
                method="POST",
                url="/api/leads/lead-create-via-telegram/",
                headers=headers,
                json=data,
                *args,
                **kwargs,
            )

        return status, result

    async def business_card_photo_ocr(self, file_data, *args, **kwargs):
        """Process a business card photo with OCR.

        Args:
            file_data: The file data to upload. This should be a bytes object or a file-like object.
                      For Telegram bot usage, you'll need to download the file from Telegram first.

        Returns:
            Tuple of (status_code, response_data)
        """
        from aiohttp import FormData

        # Create multipart form data
        form = FormData()
        form.add_field(
            "business_card_photo",
            file_data,
            filename="business_card.jpg",
            content_type="image/jpeg",
        )

        headers = {"X-Telegram-Bot-API-Token": self.api_key}
        status, result = await self._make_request(
            method="POST",
            url="/api/leads/business-card-ocr-via-telegram/",
            headers=headers,
            data=form,  # Use form data instead of JSON
            *args,
            **kwargs,
        )
        return status, result
