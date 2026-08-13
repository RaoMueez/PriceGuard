// src/services/complaintsService.js
//
// RECONSTRUCTED based on the postMultipart pattern used elsewhere in your
// app — I don't have your actual current file. If this doesn't match
// (different function/param names, different import), share your real
// file and I'll fix it in one pass instead of guessing again.

import api from "./api";

export const submitComplaint = async ({
    commodity_id,
    market_id,
    shop_name,
    complaint_type,
    amount_paid,
    quantity,
    imageUri,
    device_latitude,
    device_longitude,
}) => {
    const { data } = await api.postMultipart(
        "/api/complaints",
        {
            commodity_id,
            market_id,
            shop_name,
            complaint_type,
            amount_paid,
            quantity,
            device_latitude,
            device_longitude,
        },
        imageUri,
        "file"
    );
    return data;
};