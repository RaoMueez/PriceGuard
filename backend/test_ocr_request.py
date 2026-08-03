# test_ocr_request.py
# Temporary script — just for testing the OCR endpoint directly

import requests

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJiMmYxYjA3OC01YWRhLTQ3ZWItOTdkMC1lMzFkMzFlNjdkODkiLCJyb2xlIjoiYWRtaW4iLCJleHAiOjE3ODU4MzczNDh9.AOAXGjDcaDlNmxCmxH5712rfbPaQW8EyRxG8o0JDTEY"

url = "http://127.0.0.1:8000/api/test-ocr"

headers = {
    "Authorization": f"Bearer {TOKEN}"
}

# CHANGE THESE TWO LINES FOR EACH NEW TEST:
IMAGE_PATH = r"C:\Users\hp\Desktop\bill.jpeg"
ITEMS_TO_TEST = '["Potato"]'

files = {
    "file": ("receipt.jpg", open(IMAGE_PATH, "rb"), "image/jpeg")
}

data = {
    "item_names": ITEMS_TO_TEST,
    "receipt_type": "handwritten",
}

response = requests.post(url, headers=headers, files=files, data=data)

print("STATUS CODE:", response.status_code)
print("RAW RESPONSE TEXT:")
print(response.text)