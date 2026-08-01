// src/screens/MyComplaintsScreen.js

import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { useAppTheme } from "../context/ThemeContext";

export default function MyComplaintsScreen() {
    const { theme } = useAppTheme();
    return (
        <View style={[styles.container, { backgroundColor: theme.background }]}>
            <Text style={{ color: theme.text, fontSize: 18, fontWeight: "600" }}>My Reports</Text>
            <Text style={{ color: theme.textSecondary, marginTop: 8 }}>Coming soon — list of your submitted complaints.</Text>
        </View>
    );
}

const styles = StyleSheet.create({
    container: { flex: 1, justifyContent: "center", alignItems: "center", padding: 20 },
});