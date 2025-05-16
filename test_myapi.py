import asyncio
import traceback

from infrastructure.some_api.api import MyApi
from tgbot.config import load_config


async def test_api_endpoints():
    config = load_config(".env")
    api = MyApi(config)

    telegram_id = 123456789  # Replace with a real telegram_id if needed
    company_id = 1  # Replace with a real company_id if needed

    print("\n=== TESTING API ENDPOINTS ===\n")

    # Test register
    try:
        print("Testing register...")
        status, result = await api.register(telegram_id, company_id)
        print(f"✅ register: {status} {result}")
    except Exception as e:
        print(f"❌ Error in register: {e}")
        traceback.print_exc()

    # Test login
    try:
        print("\nTesting login...")
        status, result = await api.login(telegram_id)
        print(f"✅ login: {status} {result}")
    except Exception as e:
        print(f"❌ Error in login: {e}")
        traceback.print_exc()

    # Test get_companies
    try:
        print("\nTesting get_companies...")
        status, result = await api.get_companies()
        print(f"✅ get_companies: {status} {result}")
    except Exception as e:
        print(f"❌ Error in get_companies: {e}")
        traceback.print_exc()

    # Test get_shipment_directions
    try:
        print("\nTesting get_shipment_directions...")
        status, result = await api.get_shipment_directions()
        print(f"✅ get_shipment_directions: {status}")
        if status == 200 and "results" in result:
            print(f"Found {len(result['results'])} shipment directions")
            # Display first few for reference
            for i, direction in enumerate(result["results"][:3]):
                print(f"  - ID: {direction['id']}, Name: {direction['name']}")
            if len(result["results"]) > 3:
                print(f"  - ... and {len(result['results']) - 3} more")

            # Save first shipment direction ID for create_lead test
            shipment_direction_id = (
                result["results"][0]["id"] if result["results"] else 1
            )
        else:
            print(f"Unexpected response format: {result}")
            shipment_direction_id = 1
    except Exception as e:
        print(f"❌ Error in get_shipment_directions: {e}")
        traceback.print_exc()
        shipment_direction_id = 1

    # Test create_lead with different combinations
    print("\n=== TESTING CREATE_LEAD WITH DIFFERENT VALUES ===\n")

    # Possible values to try
    company_types = ["importer_exporter", "forwarder", "agent"]
    transport_modes = ["wagons", "containers", "lcl", "air", "auto"]

    # Base lead data
    base_lead_data = {
        "telegram_id": telegram_id,
        "full_name": "Test User",
        "phone": "+1234567890",
        "company_name": "Test Company",
        "position": "Manager",
        "sphere_of_activity": "Technology",
        "email": "test@example.com",
        "cargo": "Electronics",
        "shipment_volume": "100kg",
        "shipment_directions": [shipment_direction_id],  # Using ID instead of string
    }

    # Try a few combinations
    success = False
    for company_type in company_types[:3]:  # Try first 3 to keep it reasonable
        for transport_mode in transport_modes[:3]:  # Try first 3 to keep it reasonable
            if success:
                break

            lead_data = base_lead_data.copy()
            lead_data["company_type"] = company_type
            lead_data["mode_of_transport"] = transport_mode

            try:
                print(
                    f"Trying create_lead with company_type='{company_type}', mode_of_transport='{transport_mode}'..."
                )
                status, result = await api.create_lead(lead_data)
                print(f"✅ create_lead: {status} {result}")
                success = True
                break
            except Exception as e:
                error_msg = str(e)
                print(f"❌ Failed: {error_msg}")
                # Don't print full traceback to keep output cleaner

    if not success:
        print("\nCould not find valid combination for create_lead.")
        print(
            "You may need to check with your backend team for the exact valid values."
        )

    print("\n=== API TESTING COMPLETED ===\n")


async def close_sessions():
    # This is a hack to close any lingering aiohttp sessions
    # In a real application, you should properly close sessions
    import gc

    import aiohttp

    for obj in gc.get_objects():
        if isinstance(obj, aiohttp.ClientSession) and not obj.closed:
            try:
                await obj.close()
                print("Closed an unclosed ClientSession")
            except Exception as e:
                print(f"Error closing session: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(test_api_endpoints())
    except Exception as e:
        print(f"Main error: {e}")
        traceback.print_exc()
    finally:
        # Try to clean up sessions
        try:
            asyncio.run(close_sessions())
        except Exception as e:
            print(f"Error closing sessions: {e}")
        print("Test completed.")
