"use client";

import * as React from "react";
import { Info, X } from "lucide-react";
import { StoreProvider, useStore } from "../lib/store";
import { ThemeProvider } from "../lib/theme";
import Nav from "./Nav";
import { cn } from "./ui";

function Toaster() {
  const { toasts, dismissToast } = useStore();
  return (
    <div aria-live="polite" className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-full max-w-sm flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={cn(
            "pointer-events-auto flex items-start gap-3 rounded-lg border bg-surface px-4 py-3 text-sm shadow-card",
            t.kind === "success" && "border-emerald-200 dark:border-emerald-900",
            t.kind === "error" && "border-red-200 dark:border-red-900",
            t.kind === "info" && "border-line"
          )}
        >
          <span
            className={cn(
              "mt-1.5 h-2 w-2 shrink-0 rounded-full",
              t.kind === "success" && "bg-emerald-500",
              t.kind === "error" && "bg-red-500",
              t.kind === "info" && "bg-ink-faint"
            )}
            aria-hidden="true"
          />
          <p className="flex-1 text-ink">{t.text}</p>
          <button type="button" onClick={() => dismissToast(t.id)} aria-label="Dismiss notification" className="rounded p-0.5 text-ink-faint hover:text-ink">
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      ))}
    </div>
  );
}

function ModeBanner() {
  const { mode } = useStore();
  if (mode === "mock") {
    return (
      <div className="border-b border-amber-200 dark:border-amber-900 bg-amber-50 dark:bg-amber-950/40 px-4 py-2 text-center text-xs text-amber-900 dark:text-amber-200">
        <Info className="mr-1.5 inline h-3.5 w-3.5 align-text-bottom" aria-hidden="true" />
        Mock mode: no Qloo API key is configured. Entity search and suggestions come from a small built-in sample list, not from Qloo.
      </div>
    );
  }
  if (mode === "offline") {
    return (
      <div role="alert" className="border-b border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/40 px-4 py-2 text-center text-xs text-red-800 dark:text-red-300">
        Cannot reach the server. Changes cannot be saved until it is back.
      </div>
    );
  }
  return null;
}

export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
    <StoreProvider>
      <div className="flex min-h-screen flex-col">
        <Nav />
        <ModeBanner />
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6 lg:px-8">{children}</main>
        <footer className="border-t border-line py-6 text-center text-xs text-ink-faint">
          CULTURESYNC - cultural overlap as conversation starters, never assessments.
        </footer>
      </div>
      <Toaster />
    </StoreProvider>
    </ThemeProvider>
  );
}
