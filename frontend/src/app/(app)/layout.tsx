"use client";

import { AppNav } from "@/components/app-nav";
import { ThemeToggle } from "@/components/theme-toggle";
import { UploadGlobalBanner, UploadProgressProvider } from "@/contexts/upload-progress-context";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <UploadProgressProvider>
      <div className="min-h-screen flex flex-col">
        <header className="sticky top-0 z-30 border-b border-[var(--border)] bg-[var(--card)]/90 backdrop-blur-md">
          <div className="max-w-5xl mx-auto w-full px-4 py-3 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="text-lg">💕</span>
              <span className="font-semibold bg-gradient-to-r from-rose-500 to-pink-500 bg-clip-text text-transparent">
                恋爱记录
              </span>
            </div>
            <div className="flex items-center gap-3">
              <AppNav />
              <ThemeToggle />
            </div>
          </div>
        </header>
        <UploadGlobalBanner />
        <main className="flex-1 max-w-5xl mx-auto w-full px-4 py-6">{children}</main>
        <footer className="text-center text-[10px] text-[var(--muted)] py-4 border-t border-[var(--border)]">
          用心记录，用爱回忆 💗
        </footer>
      </div>
    </UploadProgressProvider>
  );
}
