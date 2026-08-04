// src/services/complaintsService.js

import api from "./api";

export const submitComplaint = async ({
    commodity_id,
    market_id,
    shop_name,
    reported_price,
    imageUri,
    device_latitude,
    device_longitude,
}) => {
    const response = await api.postMultipart(
        "/api/complaints",
        {
            commodity_id,
            market_id,
            shop_name,
            reported_price,
            device_latitude,
            device_longitude,
        },
        imageUri,
        "file"
    );
    return response.data;
};