"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Moon, Share2, Sun } from "lucide-react";
import { useStore } from "../lib/store";
import { useTheme } from "../lib/theme";
import { Badge, cn } from "./ui";

const links = [
  { href: "/", label: "Overview" },
  { href: "/workspace", label: "Workspace" },
  { href: "/agent", label: "Agent" },
  { href: "/map", label: "Map" },
  { href: "/insights", label: "Insights" },
  { href: "/collab", label: "Collaborate" },
  { href: "/settings", label: "Settings" },
];

export default function Nav() {
  const pathname = usePathname();
  const { mode } = useStore();
  const { toggle } = useTheme();

  const modeBadge =
    mode === "live" ? (
      <Badge tone="green">Live Qloo</Badge>
    ) : mode === "mock" ? (
      <Badge tone="amber">Mock data</Badge>
    ) : mode === "checking" ? (
      <Badge>Checking</Badge>
    ) : (
      <Badge tone="red">Offline</Badge>
    );

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-paper/90 backdrop-blur">
      <div className="mx-auto flex h-14 w-full max-w-6xl items-center gap-4 px-4 sm:px-6 lg:px-8">
        <Link href="/" className="flex shrink-0 items-center gap-2 rounded-md">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-accent">
            <Share2 className="h-4 w-4 text-accent-on" aria-hidden="true" />
          </span>
          <span className="hidden text-sm font-semibold tracking-wide sm:inline">CULTURESYNC</span>
        </Link>
        <nav aria-label="Primary" className="flex flex-1 items-center gap-1 overflow-x-auto">
          {links.map((l) => {
            const active = l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "whitespace-nowrap rounded-md px-3 py-1.5 text-sm transition-colors",
                  active ? "bg-muted font-medium text-ink" : "text-ink-soft hover:text-ink"
                )}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>
        {modeBadge}
        <button
          type="button"
          onClick={toggle}
          aria-label="Toggle dark mode"
          title="Toggle dark mode"
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-line text-ink-soft transition-colors hover:text-ink"
        >
          <Sun className="hidden h-4 w-4 dark:block" aria-hidden="true" />
          <Moon className="h-4 w-4 dark:hidden" aria-hidden="true" />
        </button>
      </div>
    </header>
  );
}
