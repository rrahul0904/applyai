import { useAuth } from "@clerk/expo";
import { Redirect, Tabs } from "expo-router";
import { ActivityIndicator, View } from "react-native";

export default function TabsLayout() {
  const { isLoaded, isSignedIn } = useAuth();
  if (!isLoaded) return <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}><ActivityIndicator /></View>;
  if (!isSignedIn) return <Redirect href="/" />;
  return <Tabs screenOptions={{ headerTitleStyle: { fontWeight: "700" }, tabBarActiveTintColor: "#155eef" }}>
    <Tabs.Screen name="matches" options={{ title: "Matches" }} />
    <Tabs.Screen name="jobs" options={{ title: "Jobs" }} />
    <Tabs.Screen name="applications" options={{ title: "Applications" }} />
    <Tabs.Screen name="alerts" options={{ title: "Alerts" }} />
    <Tabs.Screen name="profile" options={{ title: "Profile" }} />
  </Tabs>;
}
