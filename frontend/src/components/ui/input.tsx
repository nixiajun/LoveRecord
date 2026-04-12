import * as React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(function Input({ className, ...props }, ref) {
  return (
    <input
      ref={ref}
      className={cn(
        "w-full rounded-xl border border-[var(--border)] bg-transparent px-3 py-2 text-sm outline-none focus:border-rose-300 focus:ring-2 focus:ring-rose-200/40 dark:focus:border-rose-700 dark:focus:ring-rose-800/30 transition-all placeholder:text-[var(--muted)]/60",
        className
      )}
      {...props}
    />
  );
});
