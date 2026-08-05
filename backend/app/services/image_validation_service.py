# app/services/image_validation_service.py

import cv2
import numpy as np

# --- Tunable thresholds (relaxed for real-world mobile camera photos,
# including handwritten receipts with only a couple of pen-written lines) ---
# Printed POS receipts cover a large fraction of the frame with dense text;
# a 2-3 line handwritten note on plain paper might cover as little as 1-2%
# of the frame. The threshold is set low enough to admit that, while a true
# blank/empty photo still lands at ~0 and correctly fails.
MIN_TEXT_EDGE_RATIO = 0.0015

SKIN_TONE_RATIO_THRESHOLD = 0.35  # unchanged — skin-tone dominance is still a strong selfie signal

# Haar Cascade face detection: kept, but made much stricter so receipt
# logos, barcodes, and stamp graphics stop registering as faces.
FACE_MIN_NEIGHBORS = 12       # was 5 — requires far more overlapping detections to count as a face
FACE_MIN_SIZE = (100, 100)    # was (60, 60) — ignores small blob-like false positives
FACE_SCALE_FACTOR = 1.1

# Dilation kernel used to thicken thin pen strokes / faint printed text
# after edge detection, so a handful of disconnected marks merge into
# detectable, contiguous shapes instead of registering as near-nothing.
DILATION_KERNEL = np.ones((4, 4), np.uint8)
DILATION_ITERATIONS = 1


def _auto_canny(gray: np.ndarray, sigma: float = 0.33) -> np.ndarray:
    """
    Computes Canny edge thresholds from the image's own median intensity
    instead of hardcoded values. This is what actually fixes the "negligible
    text/edge content" false rejection — a fixed 50/150 threshold assumes
    consistent lighting/exposure, which real phone photos (shadows, glare,
    uneven receipt paper) don't reliably have.
    """
    median = float(np.median(gray))
    lower = int(max(0, (1.0 - sigma) * median))
    upper = int(min(255, (1.0 + sigma) * median))
    return cv2.Canny(gray, lower, upper)


def _adaptive_text_mask(gray_blurred: np.ndarray) -> np.ndarray:
    """
    Binarizes the image using adaptive (local, Gaussian-weighted) thresholding
    rather than a single global threshold. This is what actually handles
    uneven lighting/shadows across a handwritten paper — each region of the
    image gets its own threshold based on its local neighborhood, so a shadow
    on one half of the page doesn't wash out faint pen strokes there.
    Returns a binary mask where ink/text pixels are white (255).
    """
    # blockSize must be odd; 25 is a reasonable neighborhood for A4/receipt-scale photos.
    mask = cv2.adaptiveThreshold(
        gray_blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,  # ink strokes (dark) become white foreground
        blockSize=25,
        C=10,
    )
    return mask


def compute_receipt_authenticity(image_bytes: bytes) -> dict:
    """
    Analyzes an uploaded image using classical OpenCV techniques (edge density,
    Haar Cascade face detection, skin-tone ratio) to estimate whether it's
    a genuine receipt image, versus a blank page or a selfie/random photo.

    Strictly OpenCV-based — Haar Cascade is a classical CV technique bundled
    with OpenCV itself (not a deep-learning/YOLO-style model).

    Tuned for real mobile-camera photos (uneven lighting, shadows, slight
    blur, receipt paper glare) rather than clean lab-condition images, and
    for sparse handwritten receipts (a few pen-written lines on plain paper)
    as well as dense printed POS receipts.

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

    # --- Preprocessing for uneven lighting (new) ---
    # CLAHE (adaptive histogram equalization) evens out shadows/glare across
    # the receipt before edge detection, and a light Gaussian blur suppresses
    # paper-texture/JPEG noise that was previously being counted as "no edges"
    # in dark regions and "noise" in bright ones.
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray_eq = clahe.apply(gray)
    gray_blurred = cv2.GaussianBlur(gray_eq, (3, 3), 0)

    # --- Signal 1: Text edge density (lighting-adaptive + handwriting-aware) ---
    # Two complementary signals are combined:
    #   - auto-Canny edges: good at catching printed text, receipt borders, logos
    #   - adaptive-threshold ink mask: good at catching faint/thin pen strokes
    #     that Canny alone often loses, especially under uneven lighting
    # The two are OR'd together, then dilated so sparse handwritten marks
    # (which are naturally thin and disconnected) merge into contiguous,
    # detectable regions rather than registering as near-empty.
    edges = _auto_canny(gray_blurred)
    ink_mask = _adaptive_text_mask(gray_blurred)
    combined = cv2.bitwise_or(edges, ink_mask)
    dilated = cv2.dilate(combined, DILATION_KERNEL, iterations=DILATION_ITERATIONS)

    text_edge_ratio = float(np.count_nonzero(dilated)) / dilated.size

    # --- Signal 2: Face detection (classical Haar Cascade, built into OpenCV) ---
    # Stricter parameters: real receipts rarely have anything resembling a
    # face at minNeighbors=12+, so this now only fires on genuinely obvious faces.
    face_cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(face_cascade_path)
    faces = face_cascade.detectMultiScale(
        gray_eq,
        scaleFactor=FACE_SCALE_FACTOR,
        minNeighbors=FACE_MIN_NEIGHBORS,
        minSize=FACE_MIN_SIZE,
    )
    face_detected = len(faces) > 0

    # --- Signal 3: Skin-tone pixel ratio (common selfie/photo indicator) ---
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    lower_skin = np.array([0, 40, 60], dtype=np.uint8)
    upper_skin = np.array([25, 180, 255], dtype=np.uint8)
    skin_mask = cv2.inRange(hsv, lower_skin, upper_skin)
    skin_tone_ratio = float(np.count_nonzero(skin_mask)) / skin_mask.size

    # --- Decision logic ---
    # Face detection alone no longer auto-rejects — it must be corroborated
    # by a meaningful skin-tone presence too. This is what fixes the false
    # positive on receipt logos/patterns: a stray "face" match on printed
    # graphics has near-zero skin-tone ratio, so it no longer gets rejected
    # on that signal alone.
    if face_detected and skin_tone_ratio > (SKIN_TONE_RATIO_THRESHOLD * 0.5):
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
            "face_detected": face_detected,
            "skin_tone_ratio": round(skin_tone_ratio, 4),
        }

    if text_edge_ratio < MIN_TEXT_EDGE_RATIO:
        return {
            "is_likely_valid_receipt": False,
            "reason": "Image has negligible text/edge content — likely blank or an invalid image.",
            "text_edge_ratio": round(text_edge_ratio, 4),
            "face_detected": face_detected,
            "skin_tone_ratio": round(skin_tone_ratio, 4),
        }

    return {
        "is_likely_valid_receipt": True,
        "reason": "Image contains sufficient text-like content and no face/skin-tone dominance.",
        "text_edge_ratio": round(text_edge_ratio, 4),
        "face_detected": face_detected,
        "skin_tone_ratio": round(skin_tone_ratio, 4),
    }