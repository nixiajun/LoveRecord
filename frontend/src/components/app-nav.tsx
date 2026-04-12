"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const links = [
  { href: "/dashboard", label: "首页", icon: "🏠" },
  { href: "/memorials", label: "纪念日", icon: "💝" },
  { href: "/uploads", label: "上传", icon: "📤" },
  { href: "/days", label: "聊天", icon: "💬" },
  { href: "/reports", label: "报表", icon: "📊" },
  { href: "/settings", label: "设置", icon: "⚙️" },
];

export function AppNav() {
  const pathname = usePathname();
  return (
    <nav className="flex flex-wrap gap-1 text-sm">
      {links.map((l) => (
        <Link
          key={l.href}
          href={l.href}
          className={cn(
            "rounded-xl px-3 py-1.5 transition-all text-xs",
            pathname === l.href || (l.href === "/reports" && pathname.startsWith("/reports"))
              ? "bg-[var(--accent-soft)] text-[var(--accent)] font-medium"
              : "text-[var(--muted)] hover:text-[var(--fg)] hover:bg-[var(--warm)]"
          )}
        >
          <span className="mr-1">{l.icon}</span>
          {l.label}
        </Link>
      ))}
    </nav>
  );
}
