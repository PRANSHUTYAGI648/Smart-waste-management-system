import requests
import time

url = "http://127.0.0.1:5000/api/update-dustbin"

waste_levels = [40, 55, 70, 85, 95, 60]

for level in waste_levels:

    data = {
        "id": 1,
        "waste_level": level
    }

    response = requests.post(url, json=data)

    print("Sending data to Flask...")
    print("Dustbin ID:", data["id"])
    print("Waste Level:", level)
    print("Response:", response.json())
    print("-" * 40)

    time.sleep(5)