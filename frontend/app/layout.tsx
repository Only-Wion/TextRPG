import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TextRPG Control Center",
  description: "Next.js frontend for the TextRPG FastAPI backend",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
