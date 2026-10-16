"use client";

import * as React from "react";
import Link from "next/link";
import { Loader2 } from "lucide-react";

export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const VARIANTS: Record<ButtonVariant, string> = {
  primary: "bg-accent text-accent-on hover:bg-accent-deep",
  secondary: "border border-line bg-surface text-ink hover:border-ink-faint",
  ghost: "text-ink-soft hover:bg-muted hover:text-ink",
  danger: "text-red-700 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/40",
};

const buttonClasses = (variant: ButtonVariant, className?: string) =>
  cn(
    "inline-flex h-9 items-center justify-center gap-2 rounded-lg px-4 text-sm font-medium transition-colors",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40",
    "disabled:pointer-events-none disabled:opacity-50",
    VARIANTS[variant],
    className
  );

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  loading?: boolean;
}

export function Button({ variant = "primary", loading = false, className, children, disabled, ...props }: ButtonProps) {
  return (
    <button type="button" className={buttonClasses(variant, className)} disabled={disabled || loading} {...props}>
      {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : null}
      {children}
    </button>
  );
}

export function ButtonLink({ href, variant = "primary", className, children }: { href: string; variant?: ButtonVariant; className?: string; children: React.ReactNode }) {
  return (
    <Link href={href} className={buttonClasses(variant, className)}>
      {children}
    </Link>
  );
}

export function Card({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn("rounded-xl border border-line bg-surface shadow-card", className)}>{children}</div>;
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={cn(
        "w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-faint",
        "focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/25",
        props.className
      )}
    />
  );
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className={cn(
        "w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink",
        "focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/25",
        props.className
      )}
    />
  );
}

interface FieldProps {
  label: string;
  error?: string | null;
  className?: string;
  children: React.ReactNode;
}

export function Field({ label, error, className, children }: FieldProps) {
  return (
    <label className={cn("block", className)}>
      <span className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-ink-soft">{label}</span>
      {children}
      {error ? (
        <span role="alert" className="mt-1.5 block text-xs text-red-700 dark:text-red-400">
          {error}
        </span>
      ) : null}
    </label>
  );
}

export type BadgeTone = "accent" | "stone" | "green" | "amber" | "red" | "blue";

export function Badge({ tone = "stone", className, children }: { tone?: BadgeTone; className?: string; children: React.ReactNode }) {
  const tones: Record<BadgeTone, string> = {
    accent: "border-accent/25 bg-accent-tint text-accent-deep",
    stone: "border-line bg-muted text-ink-soft",
    green: "border-emerald-200 dark:border-emerald-900 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300",
    amber: "border-amber-200 dark:border-amber-900 bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300",
    red: "border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-400",
    blue: "border-blue-200 dark:border-blue-900 bg-blue-50 dark:bg-blue-950/40 text-blue-800 dark:text-blue-300",
  };
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium", tones[tone], className)}>
      {children}
    </span>
  );
}

interface EmptyStateProps {
  icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean | "true" }>;
  title: string;
  body: string;
  action?: React.ReactNode;
}

export function EmptyState({ icon: Icon, title, body, action }: EmptyStateProps) {
  return (
    <Card className="flex flex-col items-center px-6 py-14 text-center">
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-muted">
        <Icon className="h-5 w-5 text-ink-soft" aria-hidden="true" />
      </div>
      <h3 className="font-display text-lg text-ink">{title}</h3>
      <p className="mt-1 max-w-sm text-sm text-ink-soft">{body}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </Card>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-ink-soft">
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
      {label}
    </span>
  );
}
