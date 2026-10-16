"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { THEME_KEY } from "./themeKey";

export type ThemeChoice = "light" | "dark" | "system";

interface ThemeValue {
  choice: ThemeChoice;
  resolved: "light" | "dark";
  setChoice: (choice: ThemeChoice) => void;
  toggle: () => void;
}

const ThemeContext = createContext<ThemeValue | null>(null);

const systemPrefersDark = () => window.matchMedia("(prefers-color-scheme: dark)").matches;

function readStoredChoice(): ThemeChoice {
  try {
    const stored = window.localStorage.getItem(THEME_KEY);
    return stored === "light" || stored === "dark" || stored === "system" ? stored : "system";
  } catch {
    return "system";
  }
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [choice, setChoiceState] = useState<ThemeChoice>("system");
  const [systemDark, setSystemDark] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setChoiceState(readStoredChoice());
    setMounted(true);
    setSystemDark(systemPrefersDark());
    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (e: MediaQueryListEvent) => setSystemDark(e.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  const resolved = choice === "system" ? (systemDark ? "dark" : "light") : choice;

  // waits for mount so the pre-paint script's class is not removed by the default state
  useEffect(() => {
    if (mounted) document.documentElement.classList.toggle("dark", resolved === "dark");
  }, [mounted, resolved]);

  const setChoice = useCallback((next: ThemeChoice) => {
    setChoiceState(next);
    try {
      window.localStorage.setItem(THEME_KEY, next);
    } catch {
      // storage blocked: theme still applies for this session
    }
  }, []);

  const toggle = useCallback(() => setChoice(resolved === "dark" ? "light" : "dark"), [resolved, setChoice]);

  const value = useMemo(() => ({ choice, resolved, setChoice, toggle }), [choice, resolved, setChoice, toggle]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used inside ThemeProvider");
  return ctx;
}
