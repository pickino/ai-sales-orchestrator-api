
import requests
import json
import os

# Define the FastAPI endpoint URL
url = "http://127.0.0.1:8001/api/generate-asset"

# Define the request payload
payload = {
    "website_url": "https://www.usaimmigration.law/",
    "company_name": "USA Immigration Lawyers",
    "save_directory": "storage/app/public/screenshots",
    "email_template": "Your email template here..."
}

# Create the save directory if it doesn't exist
os.makedirs(payload["save_directory"], exist_ok=True)

# Send the POST request
try:
    response = requests.post(url, json=payload, timeout=240)
    print(f"Status Code: {response.status_code}")
    print(f"Response text: {response.text}")
    response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

    # Print the response
    print("Request successful!")
    print("Response JSON:")
    try:
        print(json.dumps(response.json(), indent=2))
    except json.JSONDecodeError:
        print("Could not decode JSON response.")
        print("Response text:")
        print(response.text)

except requests.exceptions.RequestException as e:
    print(f"An error occurred: {e}")

