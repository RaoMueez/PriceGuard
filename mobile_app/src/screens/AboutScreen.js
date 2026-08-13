// src/screens/AboutScreen.js

import React from "react";
import { View, Text, StyleSheet, ScrollView } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useAppTheme } from "../context/ThemeContext";

export default function AboutScreen() {
    const { theme } = useAppTheme();

    return (
        <ScrollView
            style={{ backgroundColor: theme.background }}
            contentContainerStyle={styles.content}
        >
            <View style={styles.iconWrap}>
                <Ionicons name="shield-checkmark" size={48} color="#2563EB" />
            </View>

            <Text style={[styles.title, { color: theme.text }]}>PriceGuard</Text>
            <Text style={[styles.version, { color: theme.textSecondary }]}>Version 1.0.0</Text>

            <Text style={[styles.paragraph, { color: theme.text }]}>
                PriceGuard is a citizen-driven market transparency platform built to help identify
                and reduce overpricing of essential commodities.
            </Text>

            <Text style={[styles.paragraph, { color: theme.text }]}>
                Citizens can report suspected overpricing by submitting a photo of their receipt
                along with their location. Each report is checked automatically — using computer
                vision to verify the receipt, GPS to confirm the location, and OCR to cross-check
                the reported price — before being reviewed by an administrator.
            </Text>

            <Text style={[styles.paragraph, { color: theme.text }]}>
                Beyond individual reports, PriceGuard also uses historical price trends to help
                flag unusual pricing patterns consistent with hoarding, giving administrators
                earlier visibility into potential market manipulation.
            </Text>

            <Text style={[styles.sectionTitle, { color: theme.text }]}>Our Goal</Text>
            <Text style={[styles.paragraph, { color: theme.text }]}>
                To make everyday commodity pricing more transparent and give citizens a direct,
                simple way to hold local markets accountable.
            </Text>

        </ScrollView>
    );
}

const styles = StyleSheet.create({
    content: { padding: 24, paddingBottom: 60, alignItems: "center" },
    iconWrap: { marginTop: 12, marginBottom: 10 },
    title: { fontSize: 22, fontWeight: "800" },
    version: { fontSize: 12, marginBottom: 20 },
    sectionTitle: {
        fontSize: 15,
        fontWeight: "700",
        alignSelf: "flex-start",
        marginTop: 8,
        marginBottom: 6,
    },
    paragraph: { fontSize: 14, lineHeight: 21, marginBottom: 14, textAlign: "left", alignSelf: "stretch" },
    footer: { fontSize: 12, marginTop: 20, fontStyle: "italic" },
});