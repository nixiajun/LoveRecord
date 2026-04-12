import { cn } from "@/lib/utils";

export function Button({
  className,
  variant = "primary",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "outline" }) {
  const variants = {
    primary:
      "bg-gradient-to-r from-rose-500 to-pink-500 text-white hover:shadow-md active:scale-[0.98] disabled:opacity-50 disabled:hover:shadow-none",
    ghost: "text-[var(--muted)] hover:bg-[var(--warm)] hover:text-[var(--fg)]",
    outline: "border border-[var(--border)] hover:bg-[var(--warm)] hover:border-rose-200 dark:hover:border-rose-800",
  };
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center rounded-xl px-4 py-2 text-sm font-medium transition-all",
        variants[variant],
        className
      )}
      {...props}
    />
  );
}
