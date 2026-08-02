# app/services/ocr_service.py

import os
import re
import cv2
import numpy as np
import pytesseract
from dotenv import load_dotenv

load_dotenv()

TESSERACT_PATH = os.getenv("TESSERACT_PATH", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


# ============================================================
# 1. IMAGE PREPROCESSING (OpenCV)
# ============================================================

def preprocess_image(image_bytes: bytes) -> np.ndarray:
    """
    Takes raw image bytes (from an uploaded file) and returns a cleaned,
    OCR-ready OpenCV image using grayscale conversion, noise reduction,
    and adaptive thresholding. Tuned for rough/faded thermal receipts.
    """
    # Decode bytes into an OpenCV image
    np_array = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(np_array, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("Could not decode image. File may be corrupted or not a valid image.")

    # Step 1: Convert to grayscale — removes color noise, OCR works on intensity only
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Step 2: Resize up if image is small — improves OCR accuracy on low-res phone photos
    height, width = gray.shape
    if width < 1000:
        scale_factor = 1000 / width
        gray = cv2.resize(gray, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)

    # Step 3: Denoise — reduces speckle/grain common in thermal paper photos
    denoised = cv2.fastNlMeansDenoising(gray, h=10)

    # Step 4: Slight Gaussian blur — smooths out remaining noise before thresholding
    blurred = cv2.GaussianBlur(denoised, (3, 3), 0)

    # Step 5: Adaptive thresholding — converts to clean black/white text,
    # handles uneven lighting/faded print better than a single global threshold
    thresholded = cv2.adaptiveThreshold(
        blurred, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=31,
        C=15
    )

    # Step 6: Slight dilation — thickens thin/faded characters for better OCR recognition
    kernel = np.ones((1, 1), np.uint8)
    processed = cv2.dilate(thresholded, kernel, iterations=1)

    return processed


# ============================================================
# 2. OCR EXTRACTION
# ============================================================

def extract_text(processed_image: np.ndarray) -> str:
    """
    Runs Tesseract OCR on a preprocessed OpenCV image.
    Includes both English and Urdu language models for mixed-language receipts.
    """
    # 'eng+urd' allows Tesseract to recognize both English and Urdu script in the same pass.
    # PSM 6 assumes a uniform block of text — generally good for receipts.
    custom_config = r"--oem 3 --psm 6 -l eng+urd"

    try:
        raw_text = pytesseract.image_to_string(processed_image, config=custom_config)
    except pytesseract.TesseractError as e:
        # Fallback to English-only if Urdu language data isn't installed
        raw_text = pytesseract.image_to_string(processed_image, config=r"--oem 3 --psm 6 -l eng")

    return raw_text


# ============================================================
# 3. SYNONYM DICTIONARY (English / Roman Urdu / Urdu script)
# ============================================================

SYNONYM_DICTIONARY = {
    "Onion": ["onion", "onions", "peyaz", "pyaz", "piyaz", "پیاز"],
    "Potato": ["potato", "potatoes", "aloo", "alu", "آلو"],
    "Tomato": ["tomato", "tomatoes", "tamatar", "tmatar", "ٹماٹر"],
    "Garlic": ["garlic", "lehsan", "lasan", "لہسن"],
    "Ginger": ["ginger", "adrak", "ادرک"],
    "Cucumber": ["cucumber", "kheera", "khira", "کھیرا"],
    "Spinach": ["spinach", "palak", "پالک"],
    "Carrot": ["carrot", "carrots", "gajar", "گاجر"],
    "Cabbage": ["cabbage", "bandgobhi", "band gobhi", "بند گوبھی"],
    "Cauliflower": ["cauliflower", "gobhi", "phool gobhi", "گوبھی"],
    "Green Chili": ["green chili", "green chilli", "hari mirch", "ہری مرچ"],
    "Capsicum": ["capsicum", "shimla mirch", "شملہ مرچ"],

    "Apple": ["apple", "apples", "seb", "سیب"],
    "Banana": ["banana", "bananas", "kela", "kaila", "کیلا"],
    "Mango": ["mango", "mangoes", "aam", "آم"],
    "Orange": ["orange", "oranges", "santra", "musammi", "سنترہ"],
    "Guava": ["guava", "amrood", "امرود"],
    "Grapes": ["grapes", "angoor", "انگور"],
    "Watermelon": ["watermelon", "tarbooz", "tarbuz", "تربوز"],
    "Papaya": ["papaya", "papita", "پپیتا"],
    "Pomegranate": ["pomegranate", "anar", "انار"],
    "Peach": ["peach", "aarhu", "aroo", "آڑو"],
    "Plum": ["plum", "aloo bukhara", "آلو بخارا"],
    "Melon": ["melon", "kharbooza", "kharbuza", "خربوزہ"],

    "Eggs": ["eggs", "egg", "anda", "انڈا", "انڈے"],
    "Milk": ["milk", "doodh", "دودھ"],
    "Yoghurt": ["yoghurt", "yogurt", "dahi", "دہی"],

    "Chicken (Farm Gate Rate)": ["chicken farm", "farm chicken", "murgha farm", "مرغا فارم"],
    "Chicken (Processed Rate)": ["chicken processed", "processed chicken", "murgha", "مرغا", "chicken meat"],
    "Beef Meat": ["beef", "gaye ka gosht", "beef meat", "گائے کا گوشت"],
    "Mutton": ["mutton", "bakre ka gosht", "بکرے کا گوشت"],
}


# ============================================================
# 4. MULTI-ITEM SEARCH LOGIC (Regex price extraction)
# ============================================================

# Matches numbers like: 120, 120.50, 1,200, Rs 120, Rs. 120/-, 120/kg
PRICE_PATTERN = re.compile(r"(?:rs\.?|pkr)?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)\s*(?:/-|/kg|/-\s*kg)?", re.IGNORECASE)


def find_item_prices(ocr_text: str, requested_items: list[str]) -> dict:
    """
    Searches the OCR-extracted text for each requested item (using the synonym
    dictionary for Urdu/Roman Urdu matching) and extracts the nearest price
    found on the same line using regex.

    Args:
        ocr_text: Raw text extracted from the receipt image.
        requested_items: List of commodity names the user selected (e.g., ["Onion", "Tomato"]).

    Returns:
        A dict mapping each requested item to its extracted price (or None if not found).
    """
    results = {}
    lines = ocr_text.lower().split("\n")

    for item_name in requested_items:
        found_price = None
        matched_line = None

        # Get all known synonyms for this item (fallback to the item name itself if not in dictionary)
        synonyms = SYNONYM_DICTIONARY.get(item_name, [item_name.lower()])
        synonyms_lower = [s.lower() for s in synonyms]

        for line in lines:
            line_clean = line.strip()
            if not line_clean:
                continue

            # Check if any synonym appears in this line
            if any(synonym in line_clean for synonym in synonyms_lower):
                matched_line = line_clean

                # Extract all numbers on this line, take the last one
                # (receipts typically list: item name ... quantity ... unit price ... total,
                # so the rightmost number is usually the most relevant price/total)
                matches = PRICE_PATTERN.findall(line_clean)
                if matches:
                    # Clean up commas, convert to float
                    price_str = matches[-1].replace(",", "")
                    try:
                        found_price = float(price_str)
                    except ValueError:
                        found_price = None
                break  # stop at first matching line for this item

        results[item_name] = {
            "price": found_price,
            "matched_line": matched_line,
        }

    return results


# ============================================================
# 5. FULL PIPELINE (convenience function tying it all together)
# ============================================================

def process_receipt(image_bytes: bytes, requested_items: list[str]) -> dict:
    """
    Full pipeline: preprocess image -> OCR -> extract prices for requested items.
    """
    processed_image = preprocess_image(image_bytes)
    raw_text = extract_text(processed_image)
    item_prices = find_item_prices(raw_text, requested_items)

    return {
        "raw_ocr_text": raw_text,
        "extracted_items": item_prices,
    }