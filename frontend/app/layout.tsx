import type { Metadata } from "next";
import { Source_Serif_4 } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { Nav } from "@/components/Nav";

const sourceSerif = Source_Serif_4({
  variable: "--font-source-serif",
  subsets: ["latin"],
  weight: ["600", "700"],
});

export const metadata: Metadata = {
  title: "Hospital Management System",
  description: "Team 13 Hospital Management System - Sprint 1 demo UI",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${sourceSerif.variable} min-h-screen font-sans text-stone-900 antialiased`}>
        <AuthProvider>
          <Nav />
          <main className="mx-auto max-w-5xl px-6 py-10">{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}
