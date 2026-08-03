// src/services/ocrService.js

import { BASE_URL } from "./api";
import AsyncStorage from "@react-native-async-storage/async-storage";

/**
 * Sends the captured receipt image + selected commodity name to the backend
 * OCR extraction endpoint. Always resolves to a result object — never throws
 * for OCR-related failures, so the calling screen can safely fall back to
 * manual price entry without needing a try/catch around business logic.
 *
 * Returns: { price: number|null, source: string|null, auto_detected: boolean }
 */
export const extractPriceFromReceipt = async (imageUri, commodityName) => {
  try {
    const token = await AsyncStorage.getItem("access_token");

    const formData = new FormData();
    formData.append("file", {
      uri: imageUri,
      name: "receipt.jpg",
      type: "image/jpeg",
    });
    formData.append("commodity_name", commodityName);

    const headers = {};
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    const response = await fetch(`${BASE_URL}/api/test-ocr/extract-price`, {
      method: "POST",
      headers,
      body: formData,
    });

    if (!response.ok) {
      // Backend returned an error status — treat as "couldn't detect", not a crash
      return { price: null, source: null, auto_detected: false };
    }

    const data = await response.json();
    return data;
  } catch (err) {
    // Network error, timeout, or anything unexpected — always fall back gracefully
    return { price: null, source: null, auto_detected: false };
  }
};