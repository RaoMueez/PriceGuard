// src/screens/ComplaintFormScreen.js

import React, { useState, useEffect } from "react";
import {
    View, Text, StyleSheet, TouchableOpacity, TextInput,
    Image, ScrollView, Alert, Modal, FlatList
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useAppTheme } from "../context/ThemeContext";
import { fetchMarkets } from "../services/marketsService";
import { fetchRates } from "../services/ratesService";
import { submitComplaint } from "../services/complaintsService";

export default function ComplaintFormScreen({ route, navigation }) {
    const { theme } = useAppTheme();
    const { imageUri } = route.params;

    const [markets, setMarkets] = useState([]);
    const [commodities, setCommodities] = useState([]);
    const [selectedMarket, setSelectedMarket] = useState(null);
    const [selectedCommodity, setSelectedCommodity] = useState(null);
    const [reportedPrice, setReportedPrice] = useState("");
    const [marketModalVisible, setMarketModalVisible] = useState(false);
    const [commodityModalVisible, setCommodityModalVisible] = useState(false);
    const [submitting, setSubmitting] = useState(false);

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

    const handleSubmit = async () => {
        if (!selectedMarket || !selectedCommodity || !reportedPrice) {
            Alert.alert("Missing information", "Please fill in all fields before submitting.");
            return;
        }

        setSubmitting(true);
        try {
            // NOTE: receipt_image_url currently sends the local device URI as a placeholder string.
            // Real image upload to cloud storage (returning a public URL) is handled in Phase 4
            // once the AI/OCR pipeline and storage bucket are set up.
            await submitComplaint({
                commodity_id: selectedCommodity.commodity_id,
                market_id: selectedMarket.id,
                reported_price: parseFloat(reportedPrice),
                receipt_image_url: imageUri,
            });

            Alert.alert("Submitted", "Your complaint has been submitted for review.", [
                { text: "OK", onPress: () => navigation.navigate("HomeMain") }
            ]);
        } catch (err) {
            Alert.alert("Submission failed", err?.response?.data?.detail || "Something went wrong.");
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <ScrollView style={[styles.container, { backgroundColor: theme.background }]}>
            <View style={styles.header}>
                <TouchableOpacity onPress={() => navigation.goBack()}>
                    <Ionicons name="arrow-back" size={24} color={theme.text} />
                </TouchableOpacity>
                <Text style={[styles.title, { color: theme.text }]}>Report Overpricing</Text>
            </View>

            <Image source={{ uri: imageUri }} style={styles.receiptImage} />

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

            <Text style={[styles.label, { color: theme.textSecondary }]}>PRICE YOU WERE CHARGED</Text>
            <TextInput
                style={[styles.input, { backgroundColor: theme.surface, borderColor: theme.border, color: theme.text }]}
                placeholder="e.g., 180"
                placeholderTextColor={theme.textSecondary}
                keyboardType="numeric"
                value={reportedPrice}
                onChangeText={setReportedPrice}
            />

            <TouchableOpacity
                style={[styles.submitButton, { backgroundColor: theme.primary, opacity: submitting ? 0.6 : 1 }]}
                onPress={handleSubmit}
                disabled={submitting}
            >
                <Text style={styles.submitButtonText}>{submitting ? "Submitting..." : "Submit Report"}</Text>
            </TouchableOpacity>

            {/* Market selection modal */}
            <Modal visible={marketModalVisible} animationType="slide" transparent>
                <View style={styles.modalOverlay}>
                    <View style={[styles.modalContent, { backgroundColor: theme.surface }]}>
                        <Text style={[styles.modalTitle, { color: theme.text }]}>Select Market</Text>
                        <FlatList
                            data={markets}
                            keyExtractor={(item) => item.id.toString()}
                            renderItem={({ item }) => (
                                <TouchableOpacity
                                    style={styles.modalItem}
                                    onPress={() => { setSelectedMarket(item); setMarketModalVisible(false); }}
                                >
                                    <Text style={{ color: theme.text }}>{item.name}</Text>
                                </TouchableOpacity>
                            )}
                        />
                        <TouchableOpacity onPress={() => setMarketModalVisible(false)}>
                            <Text style={{ color: theme.primary, textAlign: "center", marginTop: 12 }}>Cancel</Text>
                        </TouchableOpacity>
                    </View>
                </View>
            </Modal>

            {/* Commodity selection modal */}
            <Modal visible={commodityModalVisible} animationType="slide" transparent>
                <View style={styles.modalOverlay}>
                    <View style={[styles.modalContent, { backgroundColor: theme.surface }]}>
                        <Text style={[styles.modalTitle, { color: theme.text }]}>Select Item</Text>
                        <FlatList
                            data={commodities}
                            keyExtractor={(item) => item.commodity_id.toString()}
                            renderItem={({ item }) => (
                                <TouchableOpacity
                                    style={styles.modalItem}
                                    onPress={() => { setSelectedCommodity(item); setCommodityModalVisible(false); }}
                                >
                                    <Text style={{ color: theme.text }}>{item.name} ({item.category_name})</Text>
                                </TouchableOpacity>
                            )}
                        />
                        <TouchableOpacity onPress={() => setCommodityModalVisible(false)}>
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
    input: { padding: 14, borderRadius: 12, borderWidth: 1, marginBottom: 10 },
    submitButton: { padding: 16, borderRadius: 12, alignItems: "center", marginTop: 24, marginBottom: 40 },
    submitButtonText: { color: "#fff", fontWeight: "700", fontSize: 15 },
    modalOverlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.4)", justifyContent: "flex-end" },
    modalContent: { borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20, maxHeight: "70%" },
    modalTitle: { fontSize: 16, fontWeight: "700", marginBottom: 12 },
    modalItem: { paddingVertical: 12, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: "#ccc" },
});