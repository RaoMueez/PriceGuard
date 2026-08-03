// src/services/complaintsService.js

import api from "./api";

export const submitComplaint = async ({ commodity_id, market_id, shop_name, reported_price, receipt_image_url }) => {
    const response = await api.post("/api/complaints", {
        commodity_id,
        market_id,
        shop_name,
        reported_price,
        receipt_image_url,
    });
    return response.data;
};