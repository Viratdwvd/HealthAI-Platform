import type { Metadata } from "next";
import { Toaster } from "react-hot-toast";
import "./globals.css";
import { Providers } from "@/components/Providers";
import { ConditionalShell } from "@/components/ConditionalShell";

export const metadata: Metadata = {
  title: "HealthAI Platform",
  description: "Production-grade healthcare intelligence platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300..700;1,9..40,300..500&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="h-full bg-surface-950 text-slate-100 font-sans antialiased">
        <Providers>
          <ConditionalShell>{children}</ConditionalShell>
          <Toaster
            position="top-right"
            toastOptions={{
              style: { background: "#1e293b", color: "#f1f5f9", border: "1px solid #334155" },
            }}
          />
        </Providers>
      </body>
    </html>
  );
}
