// src/screens/CategoryRatesScreen.js

import React from "react";
import { View, Text, StyleSheet, FlatList, TouchableOpacity } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useAppTheme } from "../context/ThemeContext";

export default function CategoryRatesScreen({ route, navigation }) {
    const { theme } = useAppTheme();
    const { category, iconColor, iconName } = route.params;

    return (
        <View style={[styles.container, { backgroundColor: theme.background }]}>
            <View style={styles.header}>
                <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backButton}>
                    <Ionicons name="arrow-back" size={24} color={theme.text} />
                </TouchableOpacity>
                <Text style={[styles.title, { color: theme.text }]}>{category?.category_name}</Text>
            </View>

            <FlatList
                data={category?.commodities || []}
                keyExtractor={(item) => item.commodity_id.toString()}
                contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 30 }}
                renderItem={({ item }) => (
                    <View style={[styles.row, { backgroundColor: theme.surface, borderColor: theme.border }]}>
                        <View style={[styles.dot, { backgroundColor: iconColor }]} />
                        <View style={{ flex: 1 }}>
                            <Text style={[styles.itemName, { color: theme.text }]}>{item.name}</Text>
                            <Text style={[styles.itemUnit, { color: theme.textSecondary }]}>per {item.unit}</Text>
                        </View>
                        <Text style={[styles.price, { color: theme.text }]}>
                            {item.price !== null ? `Rs. ${item.price}` : "N/A"}
                        </Text>
                    </View>
                )}
            />
        </View>
    );
}

const styles = StyleSheet.create({
    container: { flex: 1, paddingTop: 60 },
    header: { flexDirection: "row", alignItems: "center", paddingHorizontal: 20, marginBottom: 20 },
    backButton: { marginRight: 14 },
    title: { fontSize: 22, fontWeight: "700" },
    row: {
        flexDirection: "row", alignItems: "center", padding: 14,
        borderRadius: 12, borderWidth: 1, marginBottom: 10,
    },
    dot: { width: 8, height: 8, borderRadius: 4, marginRight: 12 },
    itemName: { fontSize: 15, fontWeight: "600" },
    itemUnit: { fontSize: 12, marginTop: 2 },
    price: { fontSize: 16, fontWeight: "700" },
});