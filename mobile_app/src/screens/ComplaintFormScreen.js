// src/screens/ComplaintFormScreen.js

import React, { useState, useEffect } from "react";
import {
    View, Text, StyleSheet, TouchableOpacity, TextInput,
    Image, ScrollView, Alert, Modal, FlatList, ActivityIndicator
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useAppTheme } from "../context/ThemeContext";
import { fetchMarkets } from "../services/marketsService";
import { fetchRates } from "../services/ratesService";
import { submitComplaint } from "../services/complaintsService";
import { extractPriceFromReceipt } from "../services/ocrService";

const COMPLAINT_TYPES = [
    { value: "overpricing", label: "Overpricing", icon: "trending-up-outline" },
    { value: "short_weight", label: "Short Weight", icon: "scale-outline" },
];

export default function ComplaintFormScreen({ route, navigation }) {
    const { theme } = useAppTheme();
    const { imageUri, deviceLatitude, deviceLongitude } = route.params;

    const [markets, setMarkets] = useState([]);
    const [commodities, setCommodities] = useState([]);
    const [selectedMarket, setSelectedMarket] = useState(null);
    const [selectedCommodity, setSelectedCommodity] = useState(null);
    const [shopName, setShopName] = useState("");

    const [complaintType, setComplaintType] = useState("overpricing");
    const [amountPaid, setAmountPaid] = useState("");
    const [quantity, setQuantity] = useState("");

    const [marketModalVisible, setMarketModalVisible] = useState(false);
    const [commodityModalVisible, setCommodityModalVisible] = useState(false);
    const [marketSearch, setMarketSearch] = useState("");
    const [commoditySearch, setCommoditySearch] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [ocrStatus, setOcrStatus] = useState(null);

    useEffect(() => {
        const loadOptions = async () => {
            try {
                const marketList = await fetchMarkets();
                setMarkets(marketList);

                const rates = await fetchRates();
                const allCommodities = rates.categories.flatMap(c =>
                    c.commodities.map(item => ({ ...item, category_name: c.category_name }))
                );
                setCommodities(allCommodities);
            } catch (err) {
                Alert.alert("Error", "Could not load markets/commodities. Check your connection.");
            }
        };
        loadOptions();
    }, []);

    const filteredMarkets = markets.filter(m =>
        m.name.toLowerCase().includes(marketSearch.toLowerCase())
    );

    const filteredCommodities = commodities.filter(c =>
        c.name.toLowerCase().includes(commoditySearch.toLowerCase())
    );

    const handleCommoditySelect = async (commodity) => {
        setSelectedCommodity(commodity);
        setCommodityModalVisible(false);
        setCommoditySearch("");
        setAmountPaid("");
        setOcrStatus("detecting");

        // OCR can only ever read what's actually printed on the receipt —
        // the total amount charged. It has no way to know the fractional
        // quantity the user is separately reporting, so it only ever
        // pre-fills Amount Paid, never Quantity.
        const result = await extractPriceFromReceipt(imageUri, commodity.name);

        if (result.auto_detected && result.price !== null && result.price !== undefined) {
            setAmountPaid(String(result.price));
            setOcrStatus("detected");
        } else {
            setOcrStatus("manual");
        }
    };

    // Live-calculated effective per-unit price, shown as a hint while
    // typing — lets the user see the violation forming before they submit.
    const effectivePricePerUnit = (() => {
        const paid = parseFloat(amountPaid);
        const qty = parseFloat(quantity);
        if (!paid || !qty || qty <= 0) return null;
        return (paid / qty).toFixed(2);
    })();

    const handleSubmit = async () => {
        if (!selectedMarket || !selectedCommodity || !amountPaid || !quantity) {
            Alert.alert("Missing information", "Please fill in all fields before submitting.");
            return;
        }

        const qtyValue = parseFloat(quantity);
        if (isNaN(qtyValue) || qtyValue < 0.01) {
            Alert.alert("Invalid quantity", "Please enter a realistic quantity (at least 0.01).");
            return;
        }

        setSubmitting(true);
        try {
            await submitComplaint({
                commodity_id: selectedCommodity.commodity_id,
                market_id: selectedMarket.id,
                shop_name: shopName || null,
                complaint_type: complaintType,
                amount_paid: parseFloat(amountPaid),
                quantity: qtyValue,
                imageUri: imageUri,
                device_latitude: deviceLatitude,
                device_longitude: deviceLongitude,
            });

            Alert.alert("Submitted", "Your complaint has been submitted for review.", [
                {
                    text: "OK",
                    onPress: () => navigation.navigate("Home", { screen: "HomeMain" }),
                }
            ]);
        } catch (err) {
            Alert.alert("Submission failed", err?.response?.data?.detail || err?.message || "Something went wrong.");
        } finally {
            setSubmitting(false);
        }
    };

    const renderOcrStatus = () => {
        if (ocrStatus === "detecting") {
            return (
                <View style={styles.ocrStatusRow}>
                    <ActivityIndicator size="small" color={theme.primary} />
                    <Text style={[styles.ocrStatusText, { color: theme.textSecondary }]}>Scanning receipt for amount paid...</Text>
                </View>
            );
        }
        if (ocrStatus === "detected") {
            return (
                <View style={styles.ocrStatusRow}>
                    <Ionicons name="checkmark-circle" size={16} color={theme.primary} />
                    <Text style={[styles.ocrStatusText, { color: theme.primary }]}>
                        Amount auto-detected — please verify it's correct
                    </Text>
                </View>
            );
        }
        if (ocrStatus === "manual") {
            return (
                <View style={styles.ocrStatusRow}>
                    <Ionicons name="create-outline" size={16} color={theme.accent} />
                    <Text style={[styles.ocrStatusText, { color: theme.accent }]}>
                        Couldn't auto-read the amount — please enter it manually
                    </Text>
                </View>
            );
        }
        return null;
    };

    const quantityLabel = complaintType === "short_weight"
        ? `QUANTITY YOU ACTUALLY RECEIVED (${selectedCommodity?.unit || "kg"})`
        : `QUANTITY YOU BOUGHT (${selectedCommodity?.unit || "kg"})`;

    const quantityPlaceholder = complaintType === "short_weight"
        ? "e.g., 0.6"
        : "e.g., 0.5";

    return (
        <ScrollView style={[styles.container, { backgroundColor: theme.background }]}>
            <View style={styles.header}>
                <TouchableOpacity onPress={() => navigation.goBack()}>
                    <Ionicons name="arrow-back" size={24} color={theme.text} />
                </TouchableOpacity>
                <Text style={[styles.title, { color: theme.text }]}>Report an Issue</Text>
            </View>

            <Image source={{ uri: imageUri }} style={styles.receiptImage} />

            {/* ---------------- COMPLAINT TYPE ---------------- */}
            <Text style={[styles.label, { color: theme.textSecondary }]}>WHAT WENT WRONG?</Text>
            <View style={styles.typeRow}>
                {COMPLAINT_TYPES.map((t) => {
                    const active = complaintType === t.value;
                    return (
                        <TouchableOpacity
                            key={t.value}
                            style={[
                                styles.typeButton,
                                {
                                    backgroundColor: active ? theme.primary : theme.surface,
                                    borderColor: active ? theme.primary : theme.border,
                                },
                            ]}
                            onPress={() => setComplaintType(t.value)}
                        >
                            <Ionicons name={t.icon} size={16} color={active ? "#fff" : theme.textSecondary} />
                            <Text style={{ color: active ? "#fff" : theme.text, marginLeft: 6, fontWeight: "600" }}>
                                {t.label}
                            </Text>
                        </TouchableOpacity>
                    );
                })}
            </View>

            <Text style={[styles.label, { color: theme.textSecondary }]}>MARKET</Text>
            <TouchableOpacity
                style={[styles.selector, { backgroundColor: theme.surface, borderColor: theme.border }]}
                onPress={() => setMarketModalVisible(true)}
            >
                <Text style={{ color: selectedMarket ? theme.text : theme.textSecondary }}>
                    {selectedMarket ? selectedMarket.name : "Select a market"}
                </Text>
                <Ionicons name="chevron-down" size={18} color={theme.textSecondary} />
            </TouchableOpacity>

            <Text style={[styles.label, { color: theme.textSecondary }]}>SHOP NAME / SPECIFIC LOCATION</Text>
            <TextInput
                style={[styles.input, { backgroundColor: theme.surface, borderColor: theme.border, color: theme.text }]}
                placeholder="e.g., Ahmed Fruit Stall, near Gate 2"
                placeholderTextColor={theme.textSecondary}
                value={shopName}
                onChangeText={setShopName}
            />

            <Text style={[styles.label, { color: theme.textSecondary }]}>ITEM</Text>
            <TouchableOpacity
                style={[styles.selector, { backgroundColor: theme.surface, borderColor: theme.border }]}
                onPress={() => setCommodityModalVisible(true)}
            >
                <Text style={{ color: selectedCommodity ? theme.text : theme.textSecondary }}>
                    {selectedCommodity ? selectedCommodity.name : "Select an item"}
                </Text>
                <Ionicons name="chevron-down" size={18} color={theme.textSecondary} />
            </TouchableOpacity>

            {selectedCommodity && (
                <Text style={[styles.officialPriceHint, { color: theme.textSecondary }]}>
                    Official rate: {selectedCommodity.price ? `Rs. ${selectedCommodity.price}` : "Not available"} / {selectedCommodity.unit}
                </Text>
            )}

            {/* ---------------- AMOUNT PAID ---------------- */}
            <Text style={[styles.label, { color: theme.textSecondary }]}>AMOUNT PAID (Rs.)</Text>
            {renderOcrStatus()}
            <TextInput
                style={[styles.input, { backgroundColor: theme.surface, borderColor: theme.border, color: theme.text }]}
                placeholder="e.g., 210"
                placeholderTextColor={theme.textSecondary}
                keyboardType="numeric"
                value={amountPaid}
                onChangeText={(text) => {
                    setAmountPaid(text);
                    if (ocrStatus === "detected") setOcrStatus("manual");
                }}
                editable={!!selectedCommodity && ocrStatus !== "detecting"}
            />

            {/* ---------------- QUANTITY ---------------- */}
            <Text style={[styles.label, { color: theme.textSecondary }]}>{quantityLabel}</Text>
            <TextInput
                style={[styles.input, { backgroundColor: theme.surface, borderColor: theme.border, color: theme.text }]}
                placeholder={quantityPlaceholder}
                placeholderTextColor={theme.textSecondary}
                keyboardType="decimal-pad"
                value={quantity}
                onChangeText={setQuantity}
                editable={!!selectedCommodity}
            />

            {/* ---------------- LIVE EFFECTIVE-PRICE HINT ---------------- */}
            {effectivePricePerUnit && selectedCommodity?.price && (
                <View
                    style={[
                        styles.hintBox,
                        {
                            backgroundColor: parseFloat(effectivePricePerUnit) > selectedCommodity.price
                                ? "rgba(220,38,38,0.1)"
                                : "rgba(34,197,94,0.1)",
                        },
                    ]}
                >
                    <Text
                        style={{
                            color: parseFloat(effectivePricePerUnit) > selectedCommodity.price ? "#DC2626" : "#16A34A",
                            fontWeight: "600",
                            fontSize: 13,
                        }}
                    >
                        ≈ Rs. {effectivePricePerUnit}/{selectedCommodity.unit} — official rate is Rs. {selectedCommodity.price}/{selectedCommodity.unit}
                    </Text>
                </View>
            )}

            <TouchableOpacity
                style={[styles.submitButton, { backgroundColor: theme.primary, opacity: submitting ? 0.6 : 1 }]}
                onPress={handleSubmit}
                disabled={submitting}
            >
                <Text style={styles.submitButtonText}>{submitting ? "Submitting..." : "Submit Report"}</Text>
            </TouchableOpacity>

            {/* Market selection modal with search */}
            <Modal visible={marketModalVisible} animationType="slide" transparent>
                <View style={styles.modalOverlay}>
                    <View style={[styles.modalContent, { backgroundColor: theme.surface }]}>
                        <Text style={[styles.modalTitle, { color: theme.text }]}>Select Market</Text>
                        <TextInput
                            style={[styles.searchInput, { backgroundColor: theme.background, borderColor: theme.border, color: theme.text }]}
                            placeholder="Search markets..."
                            placeholderTextColor={theme.textSecondary}
                            value={marketSearch}
                            onChangeText={setMarketSearch}
                        />
                        <FlatList
                            data={filteredMarkets}
                            keyExtractor={(item) => item.id.toString()}
                            renderItem={({ item }) => (
                                <TouchableOpacity
                                    style={styles.modalItem}
                                    onPress={() => { setSelectedMarket(item); setMarketModalVisible(false); setMarketSearch(""); }}
                                >
                                    <Text style={{ color: theme.text }}>{item.name}</Text>
                                </TouchableOpacity>
                            )}
                            ListEmptyComponent={<Text style={{ color: theme.textSecondary, textAlign: "center", padding: 20 }}>No markets found</Text>}
                        />
                        <TouchableOpacity onPress={() => { setMarketModalVisible(false); setMarketSearch(""); }}>
                            <Text style={{ color: theme.primary, textAlign: "center", marginTop: 12 }}>Cancel</Text>
                        </TouchableOpacity>
                    </View>
                </View>
            </Modal>

            {/* Commodity selection modal with search */}
            <Modal visible={commodityModalVisible} animationType="slide" transparent>
                <View style={styles.modalOverlay}>
                    <View style={[styles.modalContent, { backgroundColor: theme.surface }]}>
                        <Text style={[styles.modalTitle, { color: theme.text }]}>Select Item</Text>
                        <TextInput
                            style={[styles.searchInput, { backgroundColor: theme.background, borderColor: theme.border, color: theme.text }]}
                            placeholder="Search items..."
                            placeholderTextColor={theme.textSecondary}
                            value={commoditySearch}
                            onChangeText={setCommoditySearch}
                        />
                        <FlatList
                            data={filteredCommodities}
                            keyExtractor={(item) => item.commodity_id.toString()}
                            renderItem={({ item }) => (
                                <TouchableOpacity style={styles.modalItem} onPress={() => handleCommoditySelect(item)}>
                                    <Text style={{ color: theme.text }}>{item.name} ({item.category_name})</Text>
                                </TouchableOpacity>
                            )}
                            ListEmptyComponent={<Text style={{ color: theme.textSecondary, textAlign: "center", padding: 20 }}>No items found</Text>}
                        />
                        <TouchableOpacity onPress={() => { setCommodityModalVisible(false); setCommoditySearch(""); }}>
                            <Text style={{ color: theme.primary, textAlign: "center", marginTop: 12 }}>Cancel</Text>
                        </TouchableOpacity>
                    </View>
                </View>
            </Modal>
        </ScrollView>
    );
}

const styles = StyleSheet.create({
    container: { flex: 1, paddingHorizontal: 20, paddingTop: 60 },
    header: { flexDirection: "row", alignItems: "center", marginBottom: 20, gap: 14 },
    title: { fontSize: 20, fontWeight: "700" },
    receiptImage: { width: "100%", height: 180, borderRadius: 14, marginBottom: 20 },
    label: { fontSize: 12, fontWeight: "600", letterSpacing: 0.5, marginBottom: 8, marginTop: 14 },
    selector: {
        flexDirection: "row", justifyContent: "space-between", alignItems: "center",
        padding: 14, borderRadius: 12, borderWidth: 1,
    },
    officialPriceHint: { fontSize: 12, marginTop: 6 },
    ocrStatusRow: { flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 8 },
    ocrStatusText: { fontSize: 12, flex: 1 },
    input: { padding: 14, borderRadius: 12, borderWidth: 1, marginBottom: 10 },

    typeRow: { flexDirection: "row", gap: 10 },
    typeButton: {
        flexDirection: "row", alignItems: "center", justifyContent: "center",
        flex: 1, paddingVertical: 12, borderRadius: 10, borderWidth: 1,
    },

    hintBox: { padding: 12, borderRadius: 10, marginTop: 4, marginBottom: 6 },

    submitButton: { padding: 16, borderRadius: 12, alignItems: "center", marginTop: 24, marginBottom: 40 },
    submitButtonText: { color: "#fff", fontWeight: "700", fontSize: 15 },
    modalOverlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.4)", justifyContent: "flex-end" },
    modalContent: { borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20, maxHeight: "75%" },
    modalTitle: { fontSize: 16, fontWeight: "700", marginBottom: 12 },
    searchInput: { padding: 12, borderRadius: 10, borderWidth: 1, marginBottom: 12 },
    modalItem: { paddingVertical: 12, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: "#ccc" },
});