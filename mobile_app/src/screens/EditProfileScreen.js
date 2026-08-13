// src/screens/EditProfileScreen.js
//
// Fetches the real authenticated user's data on mount, and saves real
// changes via PUT /api/users/me. Email is intentionally READ-ONLY — see
// note above the endpoint in users.py for why.

import React, { useState, useEffect } from "react";
import {
    View,
    Text,
    TextInput,
    StyleSheet,
    TouchableOpacity,
    ScrollView,
    Alert,
    KeyboardAvoidingView,
    Platform,
    ActivityIndicator,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useAppTheme } from "../context/ThemeContext";
import api from "../services/api";

export default function EditProfileScreen({ navigation }) {
    const { theme } = useAppTheme();

    const [name, setName] = useState("");
    const [email, setEmail] = useState("");
    const [phone, setPhone] = useState("");
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [loadError, setLoadError] = useState(null);

    useEffect(() => {
        const loadProfile = async () => {
            setLoading(true);
            setLoadError(null);
            try {
                const { data } = await api.get("/api/users/me");
                setName(data.full_name || "");
                setEmail(data.email || "");
                setPhone(data.phone_number || "");
            } catch (err) {
                setLoadError("Couldn't load your profile.");
            } finally {
                setLoading(false);
            }
        };
        loadProfile();
    }, []);

    const handleSave = async () => {
        if (!name.trim()) {
            Alert.alert("Missing Information", "Name can't be empty.");
            return;
        }

        setSaving(true);
        try {
            // Only sends the fields this screen actually lets you change.
            // Backend only shows success by returning 200 — any non-2xx
            // response throws inside api.put(), caught below, so the success
            // alert can never fire on a failed save.
            await api.put("/api/users/me", {
                full_name: name.trim(),
                phone_number: phone.trim() || null,
            });

            Alert.alert("Saved", "Your profile has been updated.", [
                { text: "OK", onPress: () => navigation.goBack() },
            ]);
        } catch (err) {
            const message = err?.response?.data?.detail || err?.message || "Something went wrong.";
            Alert.alert("Couldn't save changes", message);
        } finally {
            setSaving(false);
        }
    };

    const initials = (name || "?")
        .split(" ")
        .filter(Boolean)
        .map((p) => p[0])
        .slice(0, 2)
        .join("")
        .toUpperCase();

    return (
        <KeyboardAvoidingView
            style={{ flex: 1, backgroundColor: theme.background }}
            behavior={Platform.OS === "ios" ? "padding" : undefined}
        >
            <View style={[styles.customHeader, { borderBottomColor: theme.border }]}>
                <TouchableOpacity onPress={() => navigation.goBack()} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
                    <Ionicons name="chevron-back" size={24} color={theme.text} />
                </TouchableOpacity>
                <Text style={[styles.customHeaderTitle, { color: theme.text }]}>Edit Profile</Text>
                <View style={{ width: 24 }} />
            </View>

            {loading ? (
                <View style={styles.centered}>
                    <ActivityIndicator size="large" color={theme.primary} />
                </View>
            ) : loadError ? (
                <View style={styles.centered}>
                    <Text style={{ color: theme.textSecondary }}>{loadError}</Text>
                </View>
            ) : (
                <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
                    <View style={styles.avatarWrap}>
                        <View style={styles.avatar}>
                            <Text style={styles.avatarInitials}>{initials}</Text>
                        </View>
                    </View>

                    <Field label="Full Name" theme={theme}>
                        <TextInput
                            style={[styles.input, { color: theme.text, borderColor: theme.textSecondary }]}
                            value={name}
                            onChangeText={setName}
                            placeholder="Your name"
                            placeholderTextColor={theme.textSecondary}
                        />
                    </Field>

                    <Field label="Email" theme={theme}>
                        <TextInput
                            style={[
                                styles.input,
                                { color: theme.textSecondary, borderColor: theme.border, backgroundColor: theme.surface },
                            ]}
                            value={email}
                            editable={false}
                        />
                        <Text style={[styles.helperText, { color: theme.textSecondary }]}>
                            Email can't be changed here.
                        </Text>
                    </Field>

                    <Field label="Phone Number" theme={theme}>
                        <TextInput
                            style={[styles.input, { color: theme.text, borderColor: theme.textSecondary }]}
                            value={phone}
                            onChangeText={setPhone}
                            placeholder="+92 3XX XXXXXXX"
                            placeholderTextColor={theme.textSecondary}
                            keyboardType="phone-pad"
                        />
                    </Field>

                    <TouchableOpacity
                        style={[styles.saveButton, { backgroundColor: theme.primary, opacity: saving ? 0.6 : 1 }]}
                        onPress={handleSave}
                        disabled={saving}
                    >
                        {saving ? (
                            <ActivityIndicator size="small" color="#FFFFFF" />
                        ) : (
                            <>
                                <Ionicons name="checkmark-circle-outline" size={18} color="#FFFFFF" />
                                <Text style={styles.saveButtonText}>Save Changes</Text>
                            </>
                        )}
                    </TouchableOpacity>
                </ScrollView>
            )}
        </KeyboardAvoidingView>
    );
}

function Field({ label, theme, children }) {
    return (
        <View style={styles.fieldWrap}>
            <Text style={[styles.fieldLabel, { color: theme.textSecondary }]}>{label}</Text>
            {children}
        </View>
    );
}

const styles = StyleSheet.create({
    customHeader: {
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "space-between",
        paddingHorizontal: 16,
        paddingTop: 54,
        paddingBottom: 12,
        borderBottomWidth: StyleSheet.hairlineWidth,
    },
    customHeaderTitle: { fontSize: 17, fontWeight: "700" },
    centered: { flex: 1, alignItems: "center", justifyContent: "center" },

    content: { padding: 20, paddingBottom: 60 },
    avatarWrap: { alignItems: "center", marginBottom: 28 },
    avatar: {
        width: 76,
        height: 76,
        borderRadius: 38,
        backgroundColor: "#2563EB",
        alignItems: "center",
        justifyContent: "center",
    },
    avatarInitials: { color: "#FFFFFF", fontWeight: "700", fontSize: 26 },

    fieldWrap: { marginBottom: 18 },
    fieldLabel: { fontSize: 12, fontWeight: "600", marginBottom: 6, marginLeft: 2 },
    input: {
        borderWidth: 1,
        borderRadius: 10,
        paddingHorizontal: 14,
        paddingVertical: 12,
        fontSize: 15,
    },
    helperText: { fontSize: 11, marginTop: 4, marginLeft: 2 },

    saveButton: {
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "center",
        borderRadius: 10,
        paddingVertical: 14,
        marginTop: 16,
    },
    saveButtonText: { color: "#FFFFFF", fontWeight: "700", fontSize: 15, marginLeft: 8 },
});