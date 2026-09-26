import type { Metadata } from "next";
import "./globals.css";
import { SideNav } from "@/components/nav/side-nav";

export const metadata: Metadata = {
  title: "Position Hub · Carolina Panthers",
  description: "What he actually plays: role mix, field maps and film for every defender, 2022–2025.",
  icons: { icon: [{ url: "/panthers-logo.png", type: "image/png" }] },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-background text-foreground antialiased">
        <SideNav />
        <div className="ai-content lg:pl-16">
          <main className="mx-auto max-w-content px-4 py-6 sm:px-6">{children}</main>
          <footer className="border-t border-ink-800 py-5 text-center text-[11px] uppercase tracking-[0.14em] text-muted/70">
            Carolina Panthers · Position Hub
          </footer>
        </div>
      </body>
    </html>
  );
}
