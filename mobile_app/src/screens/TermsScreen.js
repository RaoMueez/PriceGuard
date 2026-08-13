// src/screens/TermsScreen.js
//
// Extracted out of SettingsScreen's old Terms & Conditions Modal so it's
// real navigation, consistent with AboutScreen and EditProfileScreen.

import React from "react";
import { View, Text, StyleSheet, ScrollView } from "react-native";
import { useAppTheme } from "../context/ThemeContext";

const TERMS_TEXT = `PriceGuard — Terms & Conditions

1. Purpose
PriceGuard allows citizens to report suspected overpricing of essential commodities by submitting a receipt photo, price, and location. Reports are reviewed by administrators and used to identify and act on unfair pricing practices.

2. Accuracy of Reports
By submitting a report, you confirm that the information provided — including the price, shop, and receipt photo — is accurate to the best of your knowledge. Deliberately false or misleading reports may result in account suspension.

3. Location & Data Collection
The app collects your device's location at the time a report is submitted, solely to verify that the report originates from the reported market. This data is used for verification purposes only.

4. Review Process
All reports are subject to automated and manual review. PriceGuard does not guarantee any specific outcome or timeline for a submitted report.

5. Account Responsibility
You are responsible for maintaining the confidentiality of your account credentials and for all activity submitted under your account.

6. Changes to These Terms
These terms may be updated periodically. Continued use of the app after changes constitutes acceptance of the revised terms.

7. Contact
For questions about these terms, contact your PriceGuard system administrator.`;

export default function TermsScreen() {
    const { theme } = useAppTheme();

    return (
        <ScrollView
            style={{ backgroundColor: theme.background }}
            contentContainerStyle={styles.content}
        >
            <Text style={[styles.text, { color: theme.text }]}>{TERMS_TEXT}</Text>
        </ScrollView>
    );
}

const styles = StyleSheet.create({
    content: { padding: 20, paddingBottom: 60 },
    text: { fontSize: 13, lineHeight: 21 },
});