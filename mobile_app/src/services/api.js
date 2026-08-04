// src/services/api.js

import AsyncStorage from "@react-native-async-storage/async-storage";

const BASE_URL = "http://192.168.18.29:8000";

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
        const error = new Error(data?.detail || "Request failed");
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
export { BASE_URL };