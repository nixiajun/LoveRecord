"use client";

import { useEffect, useState } from "react";

export function ThemeToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
  }, []);

  function toggle() {
    document.documentElement.classList.toggle("dark");
    setDark(document.documentElement.classList.contains("dark"));
  }

  return (
    <button
      type="button"
      onClick={toggle}
      className="w-8 h-8 rounded-full flex items-center justify-center text-sm hover:bg-[var(--warm)] transition-colors"
      title={dark ? "切换浅色" : "切换暗色"}
    >
      {dark ? "🌙" : "☀️"}
    </button>
  );
}
