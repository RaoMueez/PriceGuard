// src/screens/SettingsScreen.js
//
// Expanded from a bare Dark/Light toggle + Log Out into a full sectioned
// settings menu. Notification toggles and the Language selector are UI-only
// for now (local state, not wired to a backend/i18n system) — flagged
// inline where relevant so it's clear what's cosmetic vs. functional.

import React, { useState, useCallback } from "react";
import {
    View,
    Text,
    StyleSheet,
    TouchableOpacity,
    Switch,
    ScrollView,
    Modal,
    Alert,
    ActivityIndicator,
} from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import { Ionicons } from "@expo/vector-icons";
import { useAppTheme } from "../context/ThemeContext";
import { useAuth } from "../context/AuthContext";
import api from "../services/api";

const FAQS = [
    {
        q: "How do I report overpricing?",
        a: "Open the camera from the Home screen, take a clear photo of your receipt, and confirm the price and location. Your report is reviewed automatically and by an administrator.",
    },
    {
        q: "Why was my report auto-rejected?",
        a: "Reports are automatically rejected if the receipt image can't be verified as a real receipt, or if the price you entered isn't actually above the official rate for that item.",
    },
    {
        q: "What does 'Pending' status mean?",
        a: "Your report passed our automated checks and is waiting for an administrator to review the receipt image and confirm the violation.",
    },
    {
        q: "Do I need to allow location access?",
        a: "Yes — your device's location is used to confirm you were actually near the market when you took the photo. Reports from far outside the selected market may be flagged.",
    },
    {
        q: "What happens if a shop is found overpricing?",
        a: "Once an administrator verifies your report, it's forwarded for follow-up action against the shop. You won't see the outcome of that action in the app, only the verification status.",
    },
    {
        q: "Is my personal information shared with the shop?",
        a: "No. Reports are reviewed by administrators only. Your identity is never shared with the shop or market being reported.",
    },
];

function SectionHeader({ title, theme }) {
    return (
        <Text style={[styles.sectionHeader, { color: theme.textSecondary }]}>{title}</Text>
    );
}

function SettingsRow({ icon, label, subtitle, onPress, right, theme, danger }) {
    const content = (
        <View style={[styles.row, { backgroundColor: theme.surface }]}>
            <View style={styles.rowLeft}>
                <View style={[styles.iconWrap, danger && styles.iconWrapDanger]}>
                    <Ionicons name={icon} size={18} color={danger ? "#DC2626" : theme.primary} />
                </View>
                <View style={{ flex: 1 }}>
                    <Text style={[styles.rowLabel, { color: danger ? "#DC2626" : theme.text }]}>
                        {label}
                    </Text>
                    {subtitle ? (
                        <Text style={[styles.rowSubtitle, { color: theme.textSecondary }]}>{subtitle}</Text>
                    ) : null}
                </View>
            </View>
            {right ?? (onPress ? <Ionicons name="chevron-forward" size={18} color={theme.textSecondary} /> : null)}
        </View>
    );

    if (!onPress) return content;
    return (
        <TouchableOpacity onPress={onPress} activeOpacity={0.7}>
            {content}
        </TouchableOpacity>
    );
}

export default function SettingsScreen({ navigation }) {
    // theme.background/text/textSecondary/primary/surface all confirmed
    // against your actual files. isDark/toggleTheme are still unverified —
    // App.js doesn't touch them either. If your Dark Mode switch was
    // already working before, this destructure is presumably already
    // correct; if not, check ThemeContext.js for the real names.
    const { theme, isDark, toggleTheme } = useAppTheme();
    const { logout } = useAuth();

    const [faqModalVisible, setFaqModalVisible] = useState(false);
    const [expandedFaqIndex, setExpandedFaqIndex] = useState(null);

    const [profile, setProfile] = useState(null);
    const [profileLoading, setProfileLoading] = useState(true);

    // Refetch every time this screen comes into focus — not just on first
    // mount — so returning here after saving a change on EditProfileScreen
    // shows the updated name immediately, without needing a manual refresh.
    useFocusEffect(
        useCallback(() => {
            let isActive = true;
            (async () => {
                setProfileLoading(true);
                try {
                    const { data } = await api.get("/api/users/me");
                    if (isActive) setProfile(data);
                } catch (err) {
                    // Non-fatal — the rest of Settings still works even if
                    // this fetch fails (e.g. transient network issue).
                } finally {
                    if (isActive) setProfileLoading(false);
                }
            })();
            return () => { isActive = false; };
        }, [])
    );

    const displayName = profile?.full_name || "PriceGuard User";
    const initials = displayName
        .split(" ")
        .filter(Boolean)
        .map((p) => p[0])
        .slice(0, 2)
        .join("")
        .toUpperCase();

    const handleLogout = () => {
        Alert.alert("Log Out", "Are you sure you want to log out?", [
            { text: "Cancel", style: "cancel" },
            { text: "Log Out", style: "destructive", onPress: logout },
        ]);
    };

    const handleEditProfile = () => {
        navigation.navigate("EditProfile");
    };

    return (
        <ScrollView
            style={{ backgroundColor: theme.background }}
            contentContainerStyle={styles.scrollContent}
        >
            <View style={[styles.profileHeader, { backgroundColor: theme.surface }]}>
                <View style={styles.avatar}>
                    {profileLoading ? (
                        <ActivityIndicator size="small" color="#FFFFFF" />
                    ) : (
                        <Text style={styles.avatarInitials}>{initials}</Text>
                    )}
                </View>
                <View style={{ flex: 1 }}>
                    <Text style={[styles.profileName, { color: theme.text }]}>
                        {profileLoading ? "Loading..." : displayName}
                    </Text>
                    <View style={styles.profileLocationRow}>
                        <Ionicons name="location-outline" size={13} color={theme.textSecondary} />
                        {/* No location field exists on the User model — this stays a static
                            placeholder until a real field is added on the backend. */}
                        <Text style={[styles.profileCity, { color: theme.textSecondary }]}>Islamabad</Text>
                    </View>
                </View>
                <TouchableOpacity onPress={handleEditProfile} style={styles.editButton}>
                    <Text style={styles.editButtonText}>Edit Profile</Text>
                </TouchableOpacity>
            </View>

            <SectionHeader title="PREFERENCES" theme={theme} />
            <SettingsRow
                icon={isDark ? "moon" : "sunny"}
                label="Dark Mode"
                theme={theme}
                right={<Switch value={isDark} onValueChange={toggleTheme} />}
            />

            <SectionHeader title="SUPPORT" theme={theme} />
            <SettingsRow
                icon="help-circle-outline"
                label="Help & FAQs"
                onPress={() => setFaqModalVisible(true)}
                theme={theme}
            />
            <SettingsRow
                icon="document-text-outline"
                label="Terms & Conditions"
                onPress={() => navigation.navigate("Terms")}
                theme={theme}
            />

            <SectionHeader title="ABOUT" theme={theme} />
            <SettingsRow
                icon="information-circle-outline"
                label="About PriceGuard"
                onPress={() => navigation.navigate("About")}
                theme={theme}
            />

            <View style={{ marginTop: 24 }}>
                <SettingsRow
                    icon="log-out-outline"
                    label="Log Out"
                    onPress={handleLogout}
                    theme={theme}
                    danger
                />
            </View>

            <Modal visible={faqModalVisible} animationType="slide">
                <View style={[styles.fullModal, { backgroundColor: theme.background }]}>
                    <View style={styles.modalHeader}>
                        <Text style={[styles.modalHeaderTitle, { color: theme.text }]}>Help & FAQs</Text>
                        <TouchableOpacity onPress={() => setFaqModalVisible(false)}>
                            <Ionicons name="close" size={26} color={theme.text} />
                        </TouchableOpacity>
                    </View>
                    <ScrollView contentContainerStyle={{ padding: 16 }}>
                        {FAQS.map((item, index) => (
                            <TouchableOpacity
                                key={index}
                                style={[styles.faqCard, { backgroundColor: theme.surface }]}
                                onPress={() => setExpandedFaqIndex(expandedFaqIndex === index ? null : index)}
                                activeOpacity={0.7}
                            >
                                <View style={styles.faqQuestionRow}>
                                    <Text style={[styles.faqQuestion, { color: theme.text }]}>{item.q}</Text>
                                    <Ionicons
                                        name={expandedFaqIndex === index ? "chevron-up" : "chevron-down"}
                                        size={16}
                                        color={theme.textSecondary}
                                    />
                                </View>
                                {expandedFaqIndex === index && (
                                    <Text style={[styles.faqAnswer, { color: theme.textSecondary }]}>{item.a}</Text>
                                )}
                            </TouchableOpacity>
                        ))}
                    </ScrollView>
                </View>
            </Modal>
        </ScrollView>
    );
}

const styles = StyleSheet.create({
    scrollContent: { padding: 16, paddingBottom: 40 },
    profileHeader: { flexDirection: "row", alignItems: "center", borderRadius: 14, padding: 16, marginBottom: 20 },
    avatar: { width: 52, height: 52, borderRadius: 26, backgroundColor: "#2563EB", alignItems: "center", justifyContent: "center", marginRight: 14 },
    avatarInitials: { color: "#FFFFFF", fontWeight: "700", fontSize: 18 },
    profileName: { fontSize: 17, fontWeight: "700" },
    profileLocationRow: { flexDirection: "row", alignItems: "center", marginTop: 2 },
    profileCity: { fontSize: 13, marginLeft: 3 },
    editButton: { borderWidth: 1, borderColor: "#2563EB", borderRadius: 8, paddingHorizontal: 12, paddingVertical: 6 },
    editButtonText: { color: "#2563EB", fontSize: 12, fontWeight: "600" },
    sectionHeader: { fontSize: 12, fontWeight: "700", letterSpacing: 0.5, marginTop: 16, marginBottom: 8, marginLeft: 4 },
    row: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", borderRadius: 12, padding: 14, marginBottom: 8 },
    rowLeft: { flexDirection: "row", alignItems: "center", flex: 1 },
    iconWrap: { width: 32, height: 32, borderRadius: 8, backgroundColor: "rgba(37,99,235,0.1)", alignItems: "center", justifyContent: "center", marginRight: 12 },
    iconWrapDanger: { backgroundColor: "rgba(220,38,38,0.1)" },
    rowLabel: { fontSize: 15, fontWeight: "600" },
    rowSubtitle: { fontSize: 12, marginTop: 2 },
    modalOverlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.5)", alignItems: "center", justifyContent: "center", padding: 24 },
    modalCard: { width: "100%", borderRadius: 16, padding: 20 },
    modalTitle: { fontSize: 17, fontWeight: "700", marginBottom: 12 },
    modalCloseButton: { marginTop: 16, alignItems: "center" },
    modalCloseText: { color: "#2563EB", fontWeight: "600" },
    fullModal: { flex: 1 },
    modalHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 16, paddingTop: 50, paddingBottom: 12 },
    modalHeaderTitle: { fontSize: 19, fontWeight: "700" },
    faqCard: { borderRadius: 12, padding: 14, marginBottom: 10 },
    faqQuestionRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
    faqQuestion: { fontSize: 14, fontWeight: "600", flex: 1, marginRight: 8 },
    faqAnswer: { fontSize: 13, marginTop: 8, lineHeight: 19 },
});