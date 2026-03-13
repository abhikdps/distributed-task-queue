import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Task Queue Dashboard",
  description: "Distributed Task Queue – real-time monitoring",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-zinc-950 text-zinc-100 antialiased">
        <header className="border-b border-zinc-800 bg-zinc-900/80 px-6 py-4">
          <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
            Task Queue
          </h1>
          <p className="mt-0.5 text-sm text-zinc-400">
            Real-time monitoring · Priority scheduling · 10M+ tasks/day
          </p>
        </header>
        <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
