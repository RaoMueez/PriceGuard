// src/screens/HomeScreen.js

import AnimatedLogo from "../components/AnimatedLogo";
import React, { useState, useCallback, useEffect } from "react";
import {
    View, Text, StyleSheet, TouchableOpacity, ScrollView,
    ActivityIndicator, Alert, RefreshControl
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import NetInfo from "@react-native-community/netinfo";

import { useAppTheme } from "../context/ThemeContext";
import { downloadAndCacheRates, getCachedRates } from "../services/ratesService";


const CATEGORIES = [
    { name: "Vegetables", icon: "leaf-outline", color: "#4CAF7D" },
    { name: "Fruits", icon: "nutrition-outline", color: "#E8974A" },
    { name: "Dairy Products", icon: "water-outline", color: "#4A90E2" },
    { name: "Poultry & Meat", icon: "restaurant-outline", color: "#D64545" },
];

export default function HomeScreen({ navigation }) {
    const { theme, isDark, toggleTheme } = useAppTheme();
    const [ratesData, setRatesData] = useState(null);
    const [syncedAt, setSyncedAt] = useState(null);
    const [loading, setLoading] = useState(true);
    const [isOffline, setIsOffline] = useState(false);

    const loadData = useCallback(async () => {
        setLoading(true);
        const netState = await NetInfo.fetch();

        if (netState.isConnected) {
            try {
                const { data, syncedAt } = await downloadAndCacheRates();
                setRatesData(data);
                setSyncedAt(syncedAt);
                setIsOffline(false);
            } catch (err) {
                // Fall back to cache if the live fetch fails
                const cached = await getCachedRates();
                setRatesData(cached.data);
                setSyncedAt(cached.syncedAt);
                setIsOffline(true);
            }
        } else {
            const cached = await getCachedRates();
            setRatesData(cached.data);
            setSyncedAt(cached.syncedAt);
            setIsOffline(true);
        }
        setLoading(false);
    }, []);

    React.useEffect(() => {
        loadData();
    }, [loadData]);


    const handleManualDownload = async () => {
        try {
            const { syncedAt } = await downloadAndCacheRates();
            setSyncedAt(syncedAt);
            setIsOffline(false);
            Alert.alert("Success", "Latest rates downloaded for offline use.");
        } catch (err) {
            Alert.alert("Failed", "Could not download rates. Check your internet connection.");
        }
    };

    const formatSyncTime = (iso) => {
        if (!iso) return "Never";
        const date = new Date(iso);
        return date.toLocaleString();
    };

    if (loading) {
        return (
            <View style={[styles.center, { backgroundColor: theme.background }]}>
                <ActivityIndicator size="large" color={theme.primary} />
            </View>
        );
    }

    return (
        <ScrollView
            style={[styles.container, { backgroundColor: theme.background }]}
            contentContainerStyle={{ paddingBottom: 40 }}
            refreshControl={<RefreshControl refreshing={false} onRefresh={loadData} />}
        >
            <View style={styles.header}>
                <View>
                    <AnimatedLogo theme={theme} />
                    <Text style={[styles.subtitle, { color: theme.textSecondary }]}>
                        Know the fair price. Every time.
                    </Text>
                </View>
                <TouchableOpacity onPress={toggleTheme} style={[styles.themeToggle, { backgroundColor: theme.surface }]}>
                    <Ionicons name={isDark ? "sunny-outline" : "moon-outline"} size={22} color={theme.text} />
                </TouchableOpacity>
            </View>

            {isOffline && (
                <View style={[styles.offlineBadge, { backgroundColor: theme.primaryLight }]}>
                    <Ionicons name="cloud-offline-outline" size={16} color={theme.primary} />
                    <Text style={[styles.offlineText, { color: theme.primary }]}>
                        Offline — Last Synced: {formatSyncTime(syncedAt)}
                    </Text>
                </View>
            )}

            <Text style={[styles.sectionLabel, { color: theme.textSecondary }]}>CATEGORIES</Text>

            <View style={styles.grid}>
                {CATEGORIES.map((cat) => {
                    const categoryData = ratesData?.categories?.find(c => c.category_name === cat.name);
                    return (
                        <TouchableOpacity
                            key={cat.name}
                            style={[styles.card, { backgroundColor: theme.surface, shadowColor: theme.cardShadow }]}
                            onPress={() => navigation.navigate("CategoryRates", { category: categoryData, iconColor: cat.color, iconName: cat.icon })}
                        >
                            <View style={[styles.iconCircle, { backgroundColor: cat.color + "22" }]}>
                                <Ionicons name={cat.icon} size={28} color={cat.color} />
                            </View>
                            <Text style={[styles.cardTitle, { color: theme.text }]}>{cat.name}</Text>
                            <Text style={[styles.cardSubtitle, { color: theme.textSecondary }]}>
                                {categoryData?.commodities?.length || 0} items
                            </Text>
                        </TouchableOpacity>
                    );
                })}
            </View>

            <TouchableOpacity
                style={[styles.downloadButton, { backgroundColor: theme.primary }]}
                onPress={handleManualDownload}
            >
                <Ionicons name="download-outline" size={18} color="#fff" />
                <Text style={styles.downloadButtonText}>Download Latest Rates</Text>
            </TouchableOpacity>

            <Text style={[styles.syncText, { color: theme.textSecondary }]}>
                Last synced: {formatSyncTime(syncedAt)}
            </Text>
        </ScrollView>
    );
}

const styles = StyleSheet.create({
    container: { flex: 1, paddingHorizontal: 20, paddingTop: 60 },
    center: { flex: 1, justifyContent: "center", alignItems: "center" },
    header: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 },
    title: { fontSize: 28, fontWeight: "700" },
    subtitle: { fontSize: 14, marginTop: 4 },
    themeToggle: { padding: 10, borderRadius: 12 },
    offlineBadge: { flexDirection: "row", alignItems: "center", padding: 10, borderRadius: 10, marginBottom: 16, gap: 6 },
    offlineText: { fontSize: 13, fontWeight: "500" },
    sectionLabel: { fontSize: 12, fontWeight: "600", letterSpacing: 1, marginBottom: 12 },
    grid: { flexDirection: "row", flexWrap: "wrap", justifyContent: "space-between" },
    card: {
        width: "48%", borderRadius: 16, padding: 16, marginBottom: 14,
        shadowOffset: { width: 0, height: 2 }, shadowOpacity: 1, shadowRadius: 8, elevation: 2,
    },
    iconCircle: { width: 48, height: 48, borderRadius: 24, justifyContent: "center", alignItems: "center", marginBottom: 10 },
    cardTitle: { fontSize: 15, fontWeight: "600" },
    cardSubtitle: { fontSize: 12, marginTop: 2 },
    downloadButton: {
        flexDirection: "row", justifyContent: "center", alignItems: "center",
        padding: 14, borderRadius: 12, marginTop: 10, gap: 8,
    },
    downloadButtonText: { color: "#fff", fontWeight: "600", fontSize: 15 },
    syncText: { textAlign: "center", fontSize: 12, marginTop: 10 },
});