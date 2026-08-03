// src/screens/SettingsScreen.js

import React from "react";
import { View, Text, StyleSheet, TouchableOpacity } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useAppTheme } from "../context/ThemeContext";
import { useAuth } from "../context/AuthContext";

export default function SettingsScreen() {
    const { theme, isDark, toggleTheme } = useAppTheme();
    const { logout } = useAuth();

    return (
        <View style={[styles.container, { backgroundColor: theme.background }]}>
            <Text style={{ color: theme.text, fontSize: 22, fontWeight: "700", marginBottom: 20 }}>Settings</Text>

            <TouchableOpacity style={[styles.row, { backgroundColor: theme.surface }]} onPress={toggleTheme}>
                <Ionicons name={isDark ? "moon" : "sunny"} size={20} color={theme.text} />
                <Text style={{ color: theme.text, marginLeft: 12 }}>
                    {isDark ? "Dark Mode" : "Light Mode"} (tap to toggle)
                </Text>
            </TouchableOpacity>

            <TouchableOpacity style={[styles.row, { backgroundColor: theme.surface, marginTop: 12 }]} onPress={logout}>
                <Ionicons name="log-out-outline" size={20} color={theme.danger} />
                <Text style={{ color: theme.danger, marginLeft: 12 }}>Log Out</Text>
            </TouchableOpacity>
        </View>
    );
}

const styles = StyleSheet.create({
    container: { flex: 1, padding: 20, paddingTop: 60 },
    row: { flexDirection: "row", alignItems: "center", padding: 16, borderRadius: 12 },
});