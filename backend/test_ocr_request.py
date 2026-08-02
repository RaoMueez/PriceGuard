# test_ocr_request.py
# Temporary script — just for testing the OCR endpoint directly

import requests

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJiMmYxYjA3OC01YWRhLTQ3ZWItOTdkMC1lMzFkMzFlNjdkODkiLCJyb2xlIjoiYWRtaW4iLCJleHAiOjE3ODU3NzI1Nzd9.MHNYib3AgJ7KJZBZ0St5lr-vfi0XPmrSYMILl_Opln0"

url = "http://127.0.0.1:8000/api/test-ocr"

headers = {
    "Authorization": f"Bearer {TOKEN}"
}

files = {
    "file": ("receipt.jpg", open(r"C:\Users\hp\Downloads\receipt.jpg", "rb"), "image/jpeg")
}

data = {
    "item_names": '["Garlic", "Tomato"]'
}

response = requests.post(url, headers=headers, files=files, data=data)

print("STATUS CODE:", response.status_code)
print("RAW RESPONSE TEXT:")
print(response.text)