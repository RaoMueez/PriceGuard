// src/services/marketsService.js

import api from "./api";

export const fetchMarkets = async () => {
    const response = await api.get("/api/markets");
    return response.data;
};