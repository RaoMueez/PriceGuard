// App.js

import React from "react";
import { View, ActivityIndicator } from "react-native";
import { NavigationContainer } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { Ionicons } from "@expo/vector-icons";

import { ThemeProvider, useAppTheme } from "./src/context/ThemeContext";
import { AuthProvider, useAuth } from "./src/context/AuthContext";

import HomeScreen from "./src/screens/HomeScreen";
import CategoryRatesScreen from "./src/screens/CategoryRatesScreen";
import CameraScreen from "./src/screens/CameraScreen";
import ComplaintFormScreen from "./src/screens/ComplaintFormScreen";
import SettingsScreen from "./src/screens/SettingsScreen";
import EditProfileScreen from "./src/screens/EditProfileScreen";
import TermsScreen from "./src/screens/TermsScreen";
import AboutScreen from "./src/screens/AboutScreen";
import LoginScreen from "./src/screens/LoginScreen";
import SignupScreen from "./src/screens/SignupScreen";

const Stack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

function AuthStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="Login" component={LoginScreen} />
      <Stack.Screen name="Signup" component={SignupScreen} />
    </Stack.Navigator>
  );
}

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

// NEW — wraps SettingsScreen plus the three screens it navigates to
// (EditProfile, Terms, About), matching the same nested-stack pattern
// already used by HomeStack and ComplaintStack. headerShown stays false,
// consistent with the rest of the app — each of these three screens
// renders its own custom back button instead of relying on a native header.
function SettingsStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="SettingsMain" component={SettingsScreen} />
      <Stack.Screen name="EditProfile" component={EditProfileScreen} />
      <Stack.Screen name="Terms" component={TermsScreen} />
      <Stack.Screen name="About" component={AboutScreen} />
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
        tabBarStyle: { backgroundColor: theme.surface, borderTopColor: theme.border },
        tabBarIcon: ({ color, size }) => {
          let iconName;
          if (route.name === "Home") iconName = "home-outline";
          else if (route.name === "Report") iconName = "camera-outline";
          else if (route.name === "Settings") iconName = "settings-outline";
          return <Ionicons name={iconName} size={size} color={color} />;
        },
      })}
    >
      <Tab.Screen name="Home" component={HomeStack} />
      <Tab.Screen name="Report" component={ComplaintStack} />
      <Tab.Screen name="Settings" component={SettingsStack} />
    </Tab.Navigator>
  );
}

function RootNavigator() {
  const { token, loading } = useAuth();
  const { theme } = useAppTheme();

  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: theme.background }}>
        <ActivityIndicator size="large" color={theme.primary} />
      </View>
    );
  }

  return (
    <NavigationContainer>
      {token ? <MainTabs /> : <AuthStack />}
    </NavigationContainer>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <RootNavigator />
      </AuthProvider>
    </ThemeProvider>
  );
}