import type { Config } from "tailwindcss";

const token = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: token("ink"), soft: token("ink-soft"), faint: token("ink-faint") },
        paper: token("paper"),
        surface: token("surface"),
        muted: token("muted"),
        line: token("line"),
        accent: { DEFAULT: token("accent"), deep: token("accent-deep"), tint: token("accent-tint"), on: token("on-accent") },
      },
      fontFamily: {
        display: ["Fraunces", "Georgia", "serif"],
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
      },
      boxShadow: { card: "var(--shadow-card)" },
    },
  },
  plugins: [],
} satisfies Config;
