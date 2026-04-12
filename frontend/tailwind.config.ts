import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        rose: {
          50: "#fff7f7",
          100: "#ffecec",
          200: "#ffd0d6",
          300: "#ffa3ad",
          400: "#ff6b7d",
          500: "#e84a63",
          600: "#c93a52",
        },
        cream: {
          50: "#fffdfb",
          100: "#fdf8f3",
          200: "#f7ebe0",
        },
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
