import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Link from "next/link";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "SEC Cyber Incident Tracker",
  description:
    "Tracking stock price impact and risk prediction gaps for SEC-disclosed material cybersecurity incidents.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`dark ${geistSans.variable} ${geistMono.variable}`}>
      <body className="bg-slate-950 text-slate-100 antialiased min-h-screen">
        <nav className="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-50">
          <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
            <Link href="/" className="font-semibold text-white tracking-tight">
              SEC Cyber Tracker
            </Link>
            <div className="flex gap-6 text-sm text-slate-400">
              <Link href="/incidents" className="hover:text-white transition-colors">
                Incidents
              </Link>
              <Link href="/methodology" className="hover:text-white transition-colors">
                Methodology
              </Link>
              <a
                href="https://efts.sec.gov/LATEST/search-index?q=%22Item+1.05%22&forms=8-K"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-white transition-colors"
              >
                EDGAR ↗
              </a>
            </div>
          </div>
        </nav>
        <main className="max-w-6xl mx-auto px-4 py-8">{children}</main>
        <footer className="border-t border-slate-800 mt-16 py-8 text-center text-xs text-slate-600">
          Data sourced from SEC EDGAR · Stock data via Yahoo Finance · Risk analysis powered by Claude
          (Anthropic) · Not investment advice
        </footer>
      </body>
    </html>
  );
}
