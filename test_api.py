import requests
import time
import sys

url = "http://127.0.0.1:5000/api/update-dustbin"

waste_levels = [40, 55, 70, 85, 95, 20]

print("Smart Waste IoT Telemetry Simulator")
print("=========================================")
print(f"Target Server URL: {url}\n")

for level in waste_levels:
    data = {
        "id": 1,
        "waste_level": level
    }

    try:
        response = requests.post(url, json=data, timeout=5)
        print(f"[ID {data['id']}] Sending Waste Level: {level}%")
        print(f"Server Response: {response.json()}")
        print("-" * 45)
    except Exception as e:
        print(f"Connection error: {e}")
        print("Ensure Flask server is running on http://127.0.0.1:5000")
        sys.exit(1)

    time.sleep(1)

print("Telemetry simulation loop completed successfully!")