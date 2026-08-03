# app/services/ocr_service.py

import os
import re
import cv2
import numpy as np
import pytesseract
from dotenv import load_dotenv
from rapidfuzz import fuzz, process as fuzzy_process

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

    "Chicken (Farm Gate Rate)": ["chicken farm", "farm chicken", "murgha farm", "مرغا فارم", "زندہ مرغی", "زندہ چکن"],
    "Chicken (Processed Rate)": ["chicken processed", "processed chicken", "murgha", "مرغا", "chicken meat", "مرغی", "چکن"],
    "Beef Meat": ["beef", "gaye ka gosht", "beef meat", "گائے کا گوشت", "بیف", "بڑا گوشت"],
    "Mutton": ["mutton", "bakre ka gosht", "بکرے کا گوشت", "مٹن", "چھوٹا گوشت"],
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


# ============================================================
# 6. NOTEBOOK LINE REMOVAL (for handwritten receipts)
# ============================================================

def remove_ruled_lines(image: np.ndarray) -> np.ndarray:
    """
    Detects and removes straight ruled lines (any color) using Hough Line
    Transform, rather than assuming a specific line color.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=100,
        minLineLength=image.shape[1] * 0.4,  # only long lines (likely ruling, not handwriting strokes)
        maxLineGap=10
    )

    mask = np.zeros(gray.shape, dtype=np.uint8)
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            # Only remove near-horizontal or near-vertical lines (actual ruling),
            # not diagonal strokes that could be handwriting
            angle = abs(np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi)
            if angle < 5 or angle > 175 or (85 < angle < 95):
                cv2.line(mask, (x1, y1), (x2, y2), 255, 3)

    cleaned = cv2.inpaint(image, mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)
    return cleaned


def preprocess_handwritten_image(image_bytes: bytes) -> np.ndarray:
    """
    Preprocessing pipeline specifically for handwritten notebook-style receipts.
    Removes ruled lines first, then applies the standard cleanup steps.
    """
    np_array = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(np_array, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("Could not decode image. File may be corrupted or not a valid image.")

    # Step 1: Remove blue ruled lines while image is still in color
    # (color info is needed to detect "blue" — must happen before grayscale)
    line_free = remove_notebook_lines(image)

    # Step 2: Convert to grayscale
    gray = cv2.cvtColor(line_free, cv2.COLOR_BGR2GRAY)

    # Step 3: Upscale if small — handwriting benefits even more than print from higher resolution
    height, width = gray.shape
    if width < 1200:
        scale_factor = 1200 / width
        gray = cv2.resize(gray, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)

    # Step 4: Denoise
    denoised = cv2.fastNlMeansDenoising(gray, h=12)

    # Step 5: Light blur
    blurred = cv2.GaussianBlur(denoised, (3, 3), 0)

    # Step 6: Adaptive threshold — larger block size tends to work better for
    # inconsistent handwriting pressure/ink darkness than printed text
    thresholded = cv2.adaptiveThreshold(
        blurred, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=41,
        C=20
    )

    return thresholded


# ============================================================
# 7. SPATIAL WORD EXTRACTION (position-aware, for handwritten layout)
# ============================================================

def extract_words_with_positions(processed_image: np.ndarray) -> list[dict]:
    """
    Runs Tesseract in 'data' mode, returning each detected word along with
    its pixel position (x, y, width, height) and confidence score.
    """
    custom_config = r"--oem 3 --psm 11 -l eng+urd"  # PSM 11: sparse text, no assumed layout

    data = pytesseract.image_to_data(
        processed_image, config=custom_config, output_type=pytesseract.Output.DICT
    )

    words = []
    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        conf = int(data["conf"][i]) if data["conf"][i] != "-1" else -1

        if text and conf > 20:  # filter out empty/very low-confidence noise
            words.append({
                "text": text,
                "x": data["left"][i],
                "y": data["top"][i],
                "width": data["width"][i],
                "height": data["height"][i],
                "conf": conf,
            })

    return words


def group_words_into_rows(words: list[dict], y_tolerance: int = 20) -> list[list[dict]]:
    """
    Groups detected words into rows based on vertical (y) proximity.
    Handwriting is rarely perfectly aligned, so words within y_tolerance
    pixels of each other are treated as being on the same line.
    """
    if not words:
        return []

    # Sort by vertical position first
    sorted_words = sorted(words, key=lambda w: w["y"])

    rows = []
    current_row = [sorted_words[0]]
    current_y = sorted_words[0]["y"]

    for word in sorted_words[1:]:
        if abs(word["y"] - current_y) <= y_tolerance:
            current_row.append(word)
        else:
            rows.append(current_row)
            current_row = [word]
            current_y = word["y"]

    rows.append(current_row)

    # Within each row, sort words left-to-right for readability
    for row in rows:
        row.sort(key=lambda w: w["x"])

    return rows


def split_row_left_right(row: list[dict], image_width: int) -> tuple[str, str]:
    """
    Splits a row's words into 'left side' (expected: price/numbers) and
    'right side' (expected: item name), based on the horizontal midpoint.
    Returns (left_text, right_text).
    """
    midpoint = image_width / 2

    left_words = [w["text"] for w in row if (w["x"] + w["width"] / 2) < midpoint]
    right_words = [w["text"] for w in row if (w["x"] + w["width"] / 2) >= midpoint]

    return " ".join(left_words), " ".join(right_words)


# ============================================================
# 8. FUZZY MATCHING + PRICE EXTRACTION FOR HANDWRITTEN ROWS
# ============================================================

def extract_number_from_text(text: str) -> float | None:
    """Extracts the first plausible number from a text fragment."""
    matches = PRICE_PATTERN.findall(text)
    if matches:
        try:
            return float(matches[0].replace(",", ""))
        except ValueError:
            return None
    return None


def find_item_prices_handwritten(
    processed_image: np.ndarray,
    requested_items: list[str],
    fuzzy_threshold: int = 65,
) -> dict:
    """
    Full spatial + fuzzy-matching pipeline for handwritten, unstructured receipts.

    For each requested item:
      1. Build the full list of known synonyms.
      2. Look through every row's right-side text, fuzzy-matching against synonyms.
      3. If a good enough match is found, extract the price from that row's left-side text.
    """
    image_width = processed_image.shape[1]

    words = extract_words_with_positions(processed_image)
    rows = group_words_into_rows(words, y_tolerance=25)

    # Precompute left/right split for every row once
    row_splits = [split_row_left_right(row, image_width) for row in rows]

    results = {}

    for item_name in requested_items:
        synonyms = SYNONYM_DICTIONARY.get(item_name, [item_name.lower()])
        best_price = None
        best_match_score = 0
        best_matched_text = None

        for left_text, right_text in row_splits:
            if not right_text.strip():
                continue

            # Compare the right-side text against every synonym, take the best score
            match = fuzzy_process.extractOne(
                right_text.lower(), synonyms, scorer=fuzz.partial_ratio
            )

            if match and match[1] >= fuzzy_threshold and match[1] > best_match_score:
                price = extract_number_from_text(left_text)
                if price is not None:
                    best_match_score = match[1]
                    best_price = price
                    best_matched_text = f"left='{left_text}' | right='{right_text}'"

        results[item_name] = {
            "price": best_price,
            "matched_line": best_matched_text,
            "confidence_score": best_match_score if best_price else None,
        }

    return results


# ============================================================
# 9. FULL HANDWRITTEN PIPELINE (convenience function)
# ============================================================

def process_handwritten_receipt(image_bytes: bytes, requested_items: list[str]) -> dict:
    """
    Full pipeline for handwritten/unstructured receipts:
    line removal -> preprocessing -> spatial OCR -> fuzzy item/price matching.
    """
    processed_image = preprocess_handwritten_image(image_bytes)
    item_prices = find_item_prices_handwritten(processed_image, requested_items)

    # Also return raw text for debugging/inspection purposes
    raw_text = extract_text(processed_image)

    return {
        "raw_ocr_text": raw_text,
        "extracted_items": item_prices,
    }