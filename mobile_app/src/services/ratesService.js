// src/services/ratesService.js

import api from "./api";
import AsyncStorage from "@react-native-async-storage/async-storage";

const RATES_CACHE_KEY = "cached_rates";
const RATES_SYNCED_AT_KEY = "rates_synced_at";

export const fetchRates = async () => {
    const response = await api.get("/api/rates");
    return response.data;
};

export const downloadAndCacheRates = async () => {
    const data = await fetchRates();
    await AsyncStorage.setItem(RATES_CACHE_KEY, JSON.stringify(data));
    const now = new Date().toISOString();
    await AsyncStorage.setItem(RATES_SYNCED_AT_KEY, now);
    return { data, syncedAt: now };
};

export const getCachedRates = async () => {
    const cached = await AsyncStorage.getItem(RATES_CACHE_KEY);
    const syncedAt = await AsyncStorage.getItem(RATES_SYNCED_AT_KEY);
    return {
        data: cached ? JSON.parse(cached) : null,
        syncedAt,
    };
};