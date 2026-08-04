# app/services/image_validation_service.py

import cv2
import numpy as np

# --- Tunable thresholds (adjust based on real-world testing) ---
MIN_TEXT_EDGE_RATIO = 0.015      # below this, image is considered "blank" / no meaningful text
SKIN_TONE_RATIO_THRESHOLD = 0.35  # above this, image is likely a selfie/person photo


def compute_receipt_authenticity(image_bytes: bytes) -> dict:
    """
    Analyzes an uploaded image using classical OpenCV techniques (edge density,
    Haar Cascade face detection, skin-tone ratio) to estimate whether it's
    a genuine receipt image, versus a blank page or a selfie/random photo.

    Strictly OpenCV-based — Haar Cascade is a classical CV technique bundled
    with OpenCV itself (not a deep-learning/YOLO-style model).

    Returns a dict with the analysis results and a final boolean verdict.
    """
    np_array = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(np_array, cv2.IMREAD_COLOR)

    if image is None:
        return {
            "is_likely_valid_receipt": False,
            "reason": "Could not decode image.",
            "text_edge_ratio": 0.0,
            "face_detected": False,
            "skin_tone_ratio": 0.0,
        }

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # --- Signal 1: Text edge density ---
    edges = cv2.Canny(gray, 50, 150)
    text_edge_ratio = float(np.count_nonzero(edges)) / edges.size

    # --- Signal 2: Face detection (classical Haar Cascade, built into OpenCV) ---
    face_cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(face_cascade_path)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    face_detected = len(faces) > 0

    # --- Signal 3: Skin-tone pixel ratio (common selfie/photo indicator) ---
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    lower_skin = np.array([0, 40, 60], dtype=np.uint8)
    upper_skin = np.array([25, 180, 255], dtype=np.uint8)
    skin_mask = cv2.inRange(hsv, lower_skin, upper_skin)
    skin_tone_ratio = float(np.count_nonzero(skin_mask)) / skin_mask.size

    # --- Decision logic ---
    if face_detected:
        return {
            "is_likely_valid_receipt": False,
            "reason": "A face was detected in the image — likely a selfie, not a receipt.",
            "text_edge_ratio": round(text_edge_ratio, 4),
            "face_detected": True,
            "skin_tone_ratio": round(skin_tone_ratio, 4),
        }

    if skin_tone_ratio > SKIN_TONE_RATIO_THRESHOLD:
        return {
            "is_likely_valid_receipt": False,
            "reason": "Image is dominated by skin-tone pixels — likely a photo of a person, not a receipt.",
            "text_edge_ratio": round(text_edge_ratio, 4),
            "face_detected": False,
            "skin_tone_ratio": round(skin_tone_ratio, 4),
        }

    if text_edge_ratio < MIN_TEXT_EDGE_RATIO:
        return {
            "is_likely_valid_receipt": False,
            "reason": "Image has negligible text/edge content — likely blank or an invalid image.",
            "text_edge_ratio": round(text_edge_ratio, 4),
            "face_detected": False,
            "skin_tone_ratio": round(skin_tone_ratio, 4),
        }

    return {
        "is_likely_valid_receipt": True,
        "reason": "Image contains sufficient text-like content and no face/skin-tone dominance.",
        "text_edge_ratio": round(text_edge_ratio, 4),
        "face_detected": False,
        "skin_tone_ratio": round(skin_tone_ratio, 4),
    }