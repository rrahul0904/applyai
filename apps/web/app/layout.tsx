import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { Geist, Geist_Mono } from "next/font/google";
import { AppProviders } from "@/components/app-providers";
import "./globals.css";
import "./platform-overrides.css";
import "./candidate-cx.css";
import "./candidate-cx-progress.css";
import "./candidate-cx-application.css";
import "./candidate-cx-resume.css";
import "./candidate-cx-plan.css";
import "./candidate-first-value.css";

const geist = Geist({ subsets: ["latin"], variable: "--font-geist" });
const geistMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-geist-mono",
});

export const metadata: Metadata = {
  title: "ApplyAI",
  description: "A structured career platform for focused job searches.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const document = (
    <html lang="en">
      <body className={`${geist.variable} ${geistMono.variable}`}>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
  return process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ? (
    <ClerkProvider>{document}</ClerkProvider>
  ) : (
    document
  );
}
