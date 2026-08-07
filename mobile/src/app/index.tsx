import { useAuth } from "@clerk/expo";
import { useHostedAuth } from "@clerk/expo/hosted-auth";
import { Redirect } from "expo-router";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";

export default function IndexScreen() {
  const { isLoaded, isSignedIn } = useAuth();
  const { startHostedAuth } = useHostedAuth();
  if (!isLoaded) return <View style={styles.center}><ActivityIndicator size="large" /></View>;
  if (isSignedIn) return <Redirect href="/(tabs)/matches" />;
  return <View style={styles.container}><Text style={styles.brand}>ApplyAI</Text><Text style={styles.title}>Your career command center, on mobile.</Text><Text style={styles.body}>Review AI matches, track applications, prepare for interviews and respond to alerts from one authenticated workspace.</Text><Pressable style={styles.button} onPress={() => startHostedAuth({ mode: "sign-in" })}><Text style={styles.buttonText}>Sign in</Text></Pressable><Pressable style={styles.secondary} onPress={() => startHostedAuth({ mode: "sign-up" })}><Text style={styles.secondaryText}>Create account</Text></Pressable></View>;
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  container: { flex: 1, justifyContent: "center", padding: 28, gap: 18, backgroundColor: "#f6f8fb" },
  brand: { fontSize: 20, fontWeight: "800", color: "#155eef" },
  title: { fontSize: 34, lineHeight: 40, fontWeight: "800", color: "#10233f" },
  body: { fontSize: 17, lineHeight: 25, color: "#53657d" },
  button: { backgroundColor: "#155eef", padding: 15, borderRadius: 12, alignItems: "center" },
  buttonText: { color: "white", fontWeight: "700", fontSize: 16 },
  secondary: { padding: 14, borderRadius: 12, borderWidth: 1, borderColor: "#ccd5e1", alignItems: "center" },
  secondaryText: { color: "#10233f", fontWeight: "700" },
});
