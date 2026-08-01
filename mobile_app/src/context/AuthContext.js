// src/context/AuthContext.js

import React, { createContext, useState, useContext, useEffect } from "react";
import AsyncStorage from "@react-native-async-storage/async-storage";

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
    const [token, setToken] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const loadToken = async () => {
            const savedToken = await AsyncStorage.getItem("access_token");
            if (savedToken) setToken(savedToken);
            setLoading(false);
        };
        loadToken();
    }, []);

    const login = async (newToken) => {
        await AsyncStorage.setItem("access_token", newToken);
        setToken(newToken);
    };

    const logout = async () => {
        await AsyncStorage.removeItem("access_token");
        setToken(null);
    };

    return (
        <AuthContext.Provider value={{ token, login, logout, loading }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => useContext(AuthContext);