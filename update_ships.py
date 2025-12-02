import asyncio
import websockets
import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo

# Your AISStream API key
API_KEY = "a9e658cdb16791cd8d2f099e96a9a6a30755e0dd"

# Tobin Bridge coordinates
BRIDGE_LAT = 42.3850
BRIDGE_LON = -71.0476

SEARCH_RADIUS = 0.5  # degrees (~30 nautical miles)
VESSEL_LIMIT = 100   # maximum vessels to collect
COLLECTION_TIMEOUT = 180  # seconds (3 minutes)

async def fetch_and_save_ships():
    """Fetch ships and save to JSON file"""

    subscribe_message = {
        "APIKey": API_KEY,
        "BoundingBoxes": [[
            [BRIDGE_LAT - SEARCH_RADIUS, BRIDGE_LON - SEARCH_RADIUS],
            [BRIDGE_LAT + SEARCH_RADIUS, BRIDGE_LON + SEARCH_RADIUS]
        ]]
    }

    print("🔍 Connecting to AISStream...")
    ships_data = []

    try:
        async with websockets.connect("wss://stream.aisstream.io/v0/stream") as websocket:
            await websocket.send(json.dumps(subscribe_message))
            print(f"✅ Connected! Collecting ships for up to {COLLECTION_TIMEOUT} seconds (or {VESSEL_LIMIT} vessels)...\n")

            start_time = time.time()
            timeout = COLLECTION_TIMEOUT

            async for message_json in websocket:
                if time.time() - start_time > timeout:
                    break

                message = json.loads(message_json)

                if "Message" in message and "PositionReport" in message["Message"]:
                    pos = message["Message"]["PositionReport"]
                    meta = message.get("MetaData", {})

                    mmsi = str(meta.get('MMSI', 'N/A'))

                    ship = {
                        'name': meta.get('ShipName', 'Unknown').strip(),
                        'mmsi': mmsi,
                        'type': meta.get('ShipType', 'Unknown'),
                        'Latitude': pos.get('Latitude'),
                        'Longitude': pos.get('Longitude'),
                        'Sog': pos.get('Sog', 0),
                        'Cog': pos.get('Cog', 0),
                        'ShipType': meta.get('ShipType', 'Unknown'),
                        'Dimension': pos.get('Dimension', {})
                    }

                    # Check if we already have this vessel (by MMSI)
                    existing_index = None
                    for i, existing_ship in enumerate(ships_data):
                        if existing_ship['mmsi'] == mmsi:
                            existing_index = i
                            break

                    if existing_index is not None:
                        # Update existing vessel with latest position
                        ships_data[existing_index] = ship
                        print(f"🔄 Updated: {ship['name']} ({len(ships_data)} unique vessels)")
                    else:
                        # New vessel
                        ships_data.append(ship)
                        print(f"📍 Captured: {ship['name']} ({len(ships_data)} unique vessels)")

                    if len(ships_data) >= VESSEL_LIMIT:
                        break

        # Save to JSON file with timestamp
        data_with_timestamp = {
            'timestamp': datetime.now(tz=ZoneInfo('America/New_York')).isoformat(),
            'vessels': ships_data
        }
        with open('current_ships.json', 'w') as f:
            json.dump(data_with_timestamp, f, indent=2)

        print(f"\n✅ Saved {len(ships_data)} ships to current_ships.json")
        print("Run the dashboard to see them!")

    except Exception as e:
        print(f"❌ Error: {e}")

# Run it
asyncio.run(fetch_and_save_ships())
