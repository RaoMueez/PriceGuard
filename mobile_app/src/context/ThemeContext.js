// src/context/ThemeContext.js

import React, { createContext, useState, useContext } from "react";
import { useColorScheme } from "react-native";
import { lightTheme, darkTheme } from "../theme/colors";

const ThemeContext = createContext();

export const ThemeProvider = ({ children }) => {
    const systemScheme = useColorScheme();
    const [isDark, setIsDark] = useState(systemScheme === "dark");

    const toggleTheme = () => setIsDark((prev) => !prev);
    const theme = isDark ? darkTheme : lightTheme;

    return (
        <ThemeContext.Provider value={{ theme, isDark, toggleTheme }}>
            {children}
        </ThemeContext.Provider>
    );
};

export const useAppTheme = () => useContext(ThemeContext);