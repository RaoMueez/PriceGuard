// src/services/api.js

import AsyncStorage from "@react-native-async-storage/async-storage";

const BASE_URL = "https://priceguard-vrpg.onrender.com";

// ------------------------------------------------------------------
// FastAPI returns `detail` as a plain STRING for custom HTTPException
// calls, but as an ARRAY of error objects for Pydantic validation
// failures (422s). Passing an array straight into Alert.alert() crashes
// the app natively ("Value for message cannot be cast from
// ReadableNativeArray to String"). This always returns a safe string,
// regardless of which shape the backend actually sent.
// ------------------------------------------------------------------
const extractErrorMessage = (data) => {
    if (!data) return "Request failed";

    if (typeof data.detail === "string") {
        return data.detail;
    }

    if (Array.isArray(data.detail) && data.detail.length > 0) {
        const first = data.detail[0];
        let msg = (first && first.msg) || "Invalid input";
        // Pydantic v2 prefixes custom field_validator messages with
        // "Value error, " — strip it for a cleaner alert.
        msg = msg.replace(/^Value error,\s*/, "");
        return msg;
    }

    return "Request failed";
};

const buildHeaders = async (extraHeaders = {}) => {
    const token = await AsyncStorage.getItem("access_token");
    const headers = {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...extraHeaders,
    };
    if (token) {
        headers.Authorization = `Bearer ${token}`;
    }
    return headers;
};

const handleResponse = async (response) => {
    const contentType = response.headers.get("content-type");
    const isJson = contentType && contentType.includes("application/json");
    const data = isJson ? await response.json() : await response.text();

    if (!response.ok) {
        const message = extractErrorMessage(data);

        // Normalize data.detail to the clean string too, so ANY code that
        // reads err.response.data.detail directly (not just err.message)
        // is also protected, not just callers that use api.js's own error.
        if (data && typeof data === "object") {
            data.detail = message;
        }

        const error = new Error(message);
        error.response = { status: response.status, data };
        throw error;
    }

    return { data, status: response.status };
};

const api = {
    get: async (path) => {
        const headers = await buildHeaders();
        const response = await fetch(`${BASE_URL}${path}`, { method: "GET", headers });
        return handleResponse(response);
    },

    post: async (path, body) => {
        const headers = await buildHeaders();
        const response = await fetch(`${BASE_URL}${path}`, {
            method: "POST",
            headers,
            body: JSON.stringify(body),
        });
        return handleResponse(response);
    },

    put: async (path, body) => {
        const headers = await buildHeaders();
        const response = await fetch(`${BASE_URL}${path}`, {
            method: "PUT",
            headers,
            body: JSON.stringify(body),
        });
        return handleResponse(response);
    },

    postForm: async (path, formData) => {
        // For login (OAuth2PasswordRequestForm expects x-www-form-urlencoded)
        const token = await AsyncStorage.getItem("access_token");
        const headers = { "Content-Type": "application/x-www-form-urlencoded" };
        if (token) headers.Authorization = `Bearer ${token}`;

        const response = await fetch(`${BASE_URL}${path}`, {
            method: "POST",
            headers,
            body: formData,
        });
        return handleResponse(response);
    },

    postFile: async (path, fileUri, fieldName = "file") => {
        const token = await AsyncStorage.getItem("access_token");
        const formData = new FormData();
        formData.append(fieldName, {
            uri: fileUri,
            name: "upload.jpg",
            type: "image/jpeg",
        });

        const headers = {};
        if (token) headers.Authorization = `Bearer ${token}`;

        const response = await fetch(`${BASE_URL}${path}`, {
            method: "POST",
            headers,
            body: formData,
        });
        return handleResponse(response);
    },

    // Step 4c :
    postMultipart: async (path, fields, fileUri, fileFieldName = "file") => {
        const token = await AsyncStorage.getItem("access_token");
        const formData = new FormData();

        formData.append(fileFieldName, {
            uri: fileUri,
            name: "receipt.jpg",
            type: "image/jpeg",
        });

        Object.entries(fields).forEach(([key, value]) => {
            if (value !== null && value !== undefined) {
                formData.append(key, String(value));
            }
        });

        const headers = {};
        if (token) headers.Authorization = `Bearer ${token}`;

        const response = await fetch(`${BASE_URL}${path}`, {
            method: "POST",
            headers,
            body: formData,
        });
        return handleResponse(response);
    },
};

export default api;
export { BASE_URL, extractErrorMessage };