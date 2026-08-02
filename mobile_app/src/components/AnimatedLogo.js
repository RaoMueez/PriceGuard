// src/components/AnimatedLogo.js

import React, { useEffect, useRef } from "react";
import { Animated, Text, StyleSheet } from "react-native";

export default function AnimatedLogo({ theme }) {
    const fadeAnim = useRef(new Animated.Value(0)).current;
    const slideAnim = useRef(new Animated.Value(12)).current;

    useEffect(() => {
        Animated.parallel([
            Animated.timing(fadeAnim, {
                toValue: 1,
                duration: 700,
                useNativeDriver: true,
            }),
            Animated.timing(slideAnim, {
                toValue: 0,
                duration: 700,
                useNativeDriver: true,
            }),
        ]).start();
    }, []);

    return (
        <Animated.Text
            style={[
                styles.title,
                {
                    color: theme.text,
                    opacity: fadeAnim,
                    transform: [{ translateY: slideAnim }],
                },
            ]}
        >
            PriceGuard
        </Animated.Text>
    );
}

const styles = StyleSheet.create({
    title: {
        fontSize: 28,
        fontWeight: "700",
        letterSpacing: 0.3,
    },
});