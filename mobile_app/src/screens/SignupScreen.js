// src/screens/SignupScreen.js

import React, { useState, useEffect, useRef } from "react";
import { View, Text, TextInput, TouchableOpacity, StyleSheet, Alert, ActivityIndicator, ScrollView } from "react-native";
import { useAppTheme } from "../context/ThemeContext";
import { BASE_URL, extractErrorMessage } from "../services/api";

const OTP_COUNTDOWN_SECONDS = 180; // 3 minutes — must match backend OTP_EXPIRY_SECONDS

export default function SignupScreen({ navigation }) {
    const { theme } = useAppTheme();
    const [fullName, setFullName] = useState("");
    const [email, setEmail] = useState("");
    const [phone, setPhone] = useState("");
    const [password, setPassword] = useState("");
    const [loading, setLoading] = useState(false);
    const [resending, setResending] = useState(false);
    const [otpMode, setOtpMode] = useState(false);
    const [otp, setOtp] = useState("");
    const [secondsLeft, setSecondsLeft] = useState(0);

    const intervalRef = useRef(null);

    const startCountdown = () => {
        if (intervalRef.current) clearInterval(intervalRef.current);
        setSecondsLeft(OTP_COUNTDOWN_SECONDS);
        intervalRef.current = setInterval(() => {
            setSecondsLeft((prev) => {
                if (prev <= 1) {
                    clearInterval(intervalRef.current);
                    return 0;
                }
                return prev - 1;
            });
        }, 1000);
    };

    // Starts the countdown the moment the screen switches into OTP mode
    // (right after a successful signup call below), and cleans up the
    // interval on unmount so it doesn't keep ticking in the background.
    useEffect(() => {
        if (otpMode) startCountdown();
        return () => {
            if (intervalRef.current) clearInterval(intervalRef.current);
        };
    }, [otpMode]);

    const formatTime = (totalSeconds) => {
        const m = Math.floor(totalSeconds / 60).toString().padStart(2, "0");
        const s = (totalSeconds % 60).toString().padStart(2, "0");
        return `${m}:${s}`;
    };

    const handleSignup = async () => {
        if (!fullName.trim() || !email.trim() || !password) {
            Alert.alert("Missing information", "Please fill in all required fields.");
            return;
        }

        setLoading(true);
        try {
            const response = await fetch(`${BASE_URL}/api/users/signup`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    full_name: fullName.trim(),
                    email,
                    phone_number: phone || null,
                    password,
                }),
            });

            const data = await response.json();

            if (!response.ok) {
                Alert.alert("Signup failed", extractErrorMessage(data));
                return;
            }

            setOtpMode(true);
            Alert.alert("Check your email", "We sent you a verification code.");
        } catch (err) {
            Alert.alert("Error", "Could not connect to the server.");
        } finally {
            setLoading(false);
        }
    };

    const handleVerify = async () => {
        if (!otp) {
            Alert.alert("Missing code", "Please enter the OTP sent to your email.");
            return;
        }

        setLoading(true);
        try {
            const response = await fetch(`${BASE_URL}/api/users/verify-email`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email, otp }),
            });

            const data = await response.json();

            if (!response.ok) {
                Alert.alert("Verification failed", extractErrorMessage(data));
                return;
            }

            Alert.alert("Success", "Email verified! You can now log in.", [
                { text: "OK", onPress: () => navigation.navigate("Login") }
            ]);
        } catch (err) {
            Alert.alert("Error", "Could not connect to the server.");
        } finally {
            setLoading(false);
        }
    };

    const handleResendOtp = async () => {
        if (secondsLeft > 0 || resending) return; // guard against the disabled state being bypassed

        setResending(true);
        try {
            const response = await fetch(`${BASE_URL}/api/users/resend-otp`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email }),
            });

            const data = await response.json();

            if (!response.ok) {
                Alert.alert("Couldn't resend", extractErrorMessage(data));
                return;
            }

            setOtp("");
            startCountdown();
            Alert.alert("Code sent", "A new verification code has been sent to your email.");
        } catch (err) {
            Alert.alert("Error", "Could not connect to the server.");
        } finally {
            setResending(false);
        }
    };

    return (
        <ScrollView style={[styles.container, { backgroundColor: theme.background }]} contentContainerStyle={{ flexGrow: 1, justifyContent: "center" }}>
            <Text style={[styles.title, { color: theme.text }]}>
                {otpMode ? "Verify Your Email" : "Create an Account"}
            </Text>

            {!otpMode ? (
                <>
                    <TextInput
                        style={[styles.input, { backgroundColor: theme.surface, borderColor: theme.border, color: theme.text }]}
                        placeholder="Full Name"
                        placeholderTextColor={theme.textSecondary}
                        value={fullName}
                        onChangeText={setFullName}
                    />
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
                        placeholder="Phone Number (optional)"
                        placeholderTextColor={theme.textSecondary}
                        keyboardType="phone-pad"
                        value={phone}
                        onChangeText={setPhone}
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
                        onPress={handleSignup}
                        disabled={loading}
                    >
                        {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Sign Up</Text>}
                    </TouchableOpacity>
                </>
            ) : (
                <>
                    <Text style={{ color: theme.textSecondary, textAlign: "center", marginBottom: 16 }}>
                        Enter the 6-digit code sent to {email}
                    </Text>
                    <TextInput
                        style={[styles.input, { backgroundColor: theme.surface, borderColor: theme.border, color: theme.text }]}
                        placeholder="123456"
                        placeholderTextColor={theme.textSecondary}
                        keyboardType="numeric"
                        value={otp}
                        onChangeText={setOtp}
                    />
                    <TouchableOpacity
                        style={[styles.button, { backgroundColor: theme.primary, opacity: loading ? 0.6 : 1 }]}
                        onPress={handleVerify}
                        disabled={loading}
                    >
                        {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Verify</Text>}
                    </TouchableOpacity>

                    <View style={styles.resendRow}>
                        {secondsLeft > 0 ? (
                            <Text style={{ color: theme.textSecondary, fontSize: 13 }}>
                                Resend OTP in {formatTime(secondsLeft)}
                            </Text>
                        ) : (
                            <TouchableOpacity onPress={handleResendOtp} disabled={resending}>
                                {resending ? (
                                    <ActivityIndicator size="small" color={theme.primary} />
                                ) : (
                                    <Text style={{ color: theme.primary, fontSize: 13, fontWeight: "700" }}>
                                        Resend OTP
                                    </Text>
                                )}
                            </TouchableOpacity>
                        )}
                    </View>
                </>
            )}

            <TouchableOpacity onPress={() => navigation.navigate("Login")} style={{ marginTop: 16 }}>
                <Text style={{ color: theme.primary, textAlign: "center" }}>Already have an account? Log in</Text>
            </TouchableOpacity>
        </ScrollView>
    );
}

const styles = StyleSheet.create({
    container: { flex: 1, paddingHorizontal: 24 },
    title: { fontSize: 24, fontWeight: "700", textAlign: "center", marginBottom: 24 },
    input: { padding: 14, borderRadius: 12, borderWidth: 1, marginBottom: 14 },
    button: { padding: 16, borderRadius: 12, alignItems: "center", marginTop: 8 },
    buttonText: { color: "#fff", fontWeight: "700", fontSize: 15 },
    resendRow: { alignItems: "center", marginTop: 16 },
});