// App.js

import React from "react";
import { NavigationContainer } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { Ionicons } from "@expo/vector-icons";

import { ThemeProvider, useAppTheme } from "./src/context/ThemeContext";
import { AuthProvider } from "./src/context/AuthContext";

import HomeScreen from "./src/screens/HomeScreen";
import CategoryRatesScreen from "./src/screens/CategoryRatesScreen";
import CameraScreen from "./src/screens/CameraScreen";
import ComplaintFormScreen from "./src/screens/ComplaintFormScreen";
import MyComplaintsScreen from "./src/screens/MyComplaintsScreen";
import SettingsScreen from "./src/screens/SettingsScreen";

const Stack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

function HomeStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="HomeMain" component={HomeScreen} />
      <Stack.Screen name="CategoryRates" component={CategoryRatesScreen} />
    </Stack.Navigator>
  );
}

function ComplaintStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="CameraCapture" component={CameraScreen} />
      <Stack.Screen name="ComplaintForm" component={ComplaintFormScreen} />
    </Stack.Navigator>
  );
}

function MainTabs() {
  const { theme } = useAppTheme();

  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarActiveTintColor: theme.primary,
        tabBarInactiveTintColor: theme.textSecondary,
        tabBarStyle: {
          backgroundColor: theme.surface,
          borderTopColor: theme.border,
        },
        tabBarIcon: ({ color, size }) => {
          let iconName;
          if (route.name === "Home") iconName = "home-outline";
          else if (route.name === "Report") iconName = "camera-outline";
          else if (route.name === "My Reports") iconName = "document-text-outline";
          else if (route.name === "Settings") iconName = "settings-outline";
          return <Ionicons name={iconName} size={size} color={color} />;
        },
      })}
    >
      <Tab.Screen name="Home" component={HomeStack} />
      <Tab.Screen name="Report" component={ComplaintStack} />
      <Tab.Screen name="My Reports" component={MyComplaintsScreen} />
      <Tab.Screen name="Settings" component={SettingsScreen} />
    </Tab.Navigator>
  );
}

function AppContent() {
  return (
    <NavigationContainer>
      <MainTabs />
    </NavigationContainer>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </ThemeProvider>
  );
}