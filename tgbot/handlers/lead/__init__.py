"""
Lead form handlers module.

This module contains handlers for the lead submission form, including:
- Form initialization and navigation
- Data collection and validation
- Final submission and confirmation
"""

from aiogram import Router

from .business_card import business_card_router
from .confirmation import confirmation_router
from .form_fields import form_fields_router
from .navigation import navigation_router

# Create a single router for all lead form handlers
lead_router = Router()

# Include all sub-routers
lead_router.include_router(business_card_router)
lead_router.include_router(
    form_fields_router
)  # form_fields before navigation if navigation relies on states set by form_fields
lead_router.include_router(navigation_router)
lead_router.include_router(confirmation_router)


__all__ = ["lead_router"]
