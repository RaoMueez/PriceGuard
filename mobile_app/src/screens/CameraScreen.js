// src/screens/CameraScreen.js

import React, { useState, useRef, useEffect } from "react";
import { View, Text, StyleSheet, TouchableOpacity } from "react-native";
import { CameraView, useCameraPermissions } from "expo-camera";
import { Ionicons } from "@expo/vector-icons";
import { useAppTheme } from "../context/ThemeContext";

export default function CameraScreen({ navigation }) {
    const { theme } = useAppTheme();
    const [permission, requestPermission] = useCameraPermissions();
    const [showHint, setShowHint] = useState(true);
    const cameraRef = useRef(null);

    useEffect(() => {
        const timer = setTimeout(() => setShowHint(false), 2500);
        return () => clearTimeout(timer);
    }, []);

    if (!permission) {
        return <View style={{ flex: 1, backgroundColor: theme.background }} />;
    }

    if (!permission.granted) {
        return (
            <View style={[styles.center, { backgroundColor: theme.background }]}>
                <Ionicons name="camera-outline" size={48} color={theme.textSecondary} />
                <Text style={[styles.permissionText, { color: theme.text }]}>
                    We need camera access to let you capture receipts.
                </Text>
                <TouchableOpacity style={[styles.permissionButton, { backgroundColor: theme.primary }]} onPress={requestPermission}>
                    <Text style={styles.permissionButtonText}>Grant Permission</Text>
                </TouchableOpacity>
            </View>
        );
    }

    const handleCapture = async () => {
        if (cameraRef.current) {
            const photo = await cameraRef.current.takePictureAsync({ quality: 0.7 });
            navigation.navigate("ComplaintForm", { imageUri: photo.uri });
        }
    };

    return (
        <View style={styles.container}>
            <CameraView style={StyleSheet.absoluteFill} ref={cameraRef} facing="back" />

            {/* Receipt framing overlay */}
            <View style={styles.overlay} pointerEvents="none">
                <View style={styles.frameBox} />
                <Text style={styles.frameLabel}>Align receipt within the frame</Text>
            </View>

            {/* Auto-dismissing hint toggle */}
            {showHint && (
                <View style={[styles.hintBanner, { backgroundColor: theme.surface }]}>
                    <Ionicons name="information-circle-outline" size={20} color={theme.primary} />
                    <Text style={[styles.hintText, { color: theme.text }]}>
                        Make sure the receipt is clear and well-lit
                    </Text>
                    <TouchableOpacity onPress={() => setShowHint(false)}>
                        <Ionicons name="close" size={20} color={theme.textSecondary} />
                    </TouchableOpacity>
                </View>
            )}

            {/* Top back button */}
            <TouchableOpacity style={styles.closeButton} onPress={() => navigation.goBack()}>
                <Ionicons name="close" size={28} color="#fff" />
            </TouchableOpacity>

            {/* Capture button */}
            <View style={styles.captureContainer}>
                <TouchableOpacity style={styles.captureButton} onPress={handleCapture}>
                    <View style={styles.captureInner} />
                </TouchableOpacity>
            </View>
        </View>
    );
}

const styles = StyleSheet.create({
    container: { flex: 1, backgroundColor: "#000" },
    center: { flex: 1, justifyContent: "center", alignItems: "center", padding: 30 },
    permissionText: { textAlign: "center", marginVertical: 16, fontSize: 15 },
    permissionButton: { paddingVertical: 12, paddingHorizontal: 24, borderRadius: 10 },
    permissionButtonText: { color: "#fff", fontWeight: "600" },

    overlay: { flex: 1, justifyContent: "center", alignItems: "center" },
    frameBox: {
        width: "82%", height: "45%",
        borderWidth: 2.5, borderColor: "#4CAF7D", borderRadius: 16,
        borderStyle: "dashed",
    },
    frameLabel: {
        color: "#fff", marginTop: 14, fontSize: 13,
        backgroundColor: "rgba(0,0,0,0.4)", paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8,
    },

    hintBanner: {
        position: "absolute", top: 60, left: 20, right: 20,
        flexDirection: "row", alignItems: "center", padding: 12,
        borderRadius: 12, gap: 10,
    },
    hintText: { flex: 1, fontSize: 13 },

    closeButton: { position: "absolute", top: 55, right: 20 },

    captureContainer: { position: "absolute", bottom: 40, alignSelf: "center" },
    captureButton: {
        width: 72, height: 72, borderRadius: 36,
        borderWidth: 4, borderColor: "#fff", justifyContent: "center", alignItems: "center",
    },
    captureInner: { width: 56, height: 56, borderRadius: 28, backgroundColor: "#fff" },
});