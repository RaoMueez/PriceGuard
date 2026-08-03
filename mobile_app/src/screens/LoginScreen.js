// src/screens/LoginScreen.js

import React, { useState } from "react";
import { View, Text, TextInput, TouchableOpacity, StyleSheet, Alert, ActivityIndicator } from "react-native";
import { useAppTheme } from "../context/ThemeContext";
import { useAuth } from "../context/AuthContext";
import { BASE_URL } from "../services/api";

export default function LoginScreen({ navigation }) {
    const { theme } = useAppTheme();
    const { login } = useAuth();
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [loading, setLoading] = useState(false);

    const handleLogin = async () => {
        if (!email || !password) {
            Alert.alert("Missing information", "Please enter both email and password.");
            return;
        }

        setLoading(true);
        try {
            const body = new URLSearchParams();
            body.append("username", email);
            body.append("password", password);

            const response = await fetch(`${BASE_URL}/api/users/login`, {
                method: "POST",
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
                body: body.toString(),
            });

            const data = await response.json();

            if (!response.ok) {
                Alert.alert("Login failed", data.detail || "Incorrect email or password.");
                return;
            }

            await login(data.access_token);
        } catch (err) {
            Alert.alert("Error", "Could not connect to the server. Check your connection.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <View style={[styles.container, { backgroundColor: theme.background }]}>
            <Text style={[styles.title, { color: theme.text }]}>Welcome to PriceGuard</Text>
            <Text style={[styles.subtitle, { color: theme.textSecondary }]}>Log in to continue</Text>

            <TextInput
                style={[styles.input, { backgroundColor: theme.surface, borderColor: theme.border, color: theme.text }]}
                placeholder="Email"
                placeholderTextColor={theme.textSecondary}
                autoCapitalize="none"
                keyboardType="email-address"
                value={email}
                onChangeText={setEmail}
            />
            <TextInput
                style={[styles.input, { backgroundColor: theme.surface, borderColor: theme.border, color: theme.text }]}
                placeholder="Password"
                placeholderTextColor={theme.textSecondary}
                secureTextEntry
                value={password}
                onChangeText={setPassword}
            />

            <TouchableOpacity
                style={[styles.button, { backgroundColor: theme.primary, opacity: loading ? 0.6 : 1 }]}
                onPress={handleLogin}
                disabled={loading}
            >
                {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Log In</Text>}
            </TouchableOpacity>

            <TouchableOpacity onPress={() => navigation.navigate("Signup")} style={{ marginTop: 16 }}>
                <Text style={{ color: theme.primary, textAlign: "center" }}>
                    Don't have an account? Sign up
                </Text>
            </TouchableOpacity>
        </View>
    );
}

const styles = StyleSheet.create({
    container: { flex: 1, justifyContent: "center", paddingHorizontal: 24 },
    title: { fontSize: 26, fontWeight: "700", textAlign: "center", marginBottom: 6 },
    subtitle: { fontSize: 14, textAlign: "center", marginBottom: 30 },
    input: { padding: 14, borderRadius: 12, borderWidth: 1, marginBottom: 14 },
    button: { padding: 16, borderRadius: 12, alignItems: "center", marginTop: 8 },
    buttonText: { color: "#fff", fontWeight: "700", fontSize: 15 },
});