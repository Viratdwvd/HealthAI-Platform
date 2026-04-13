/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  "#eef9ff",
          100: "#d8f1ff",
          200: "#b9e8ff",
          300: "#88d9ff",
          400: "#50c2fb",
          500: "#27a6f6",
          600: "#1189eb",
          700: "#0d6fd8",
          800: "#1058ae",
          900: "#134c89",
          950: "#0e2f55",
        },
        surface: {
          0:   "#ffffff",
          50:  "#f8fafc",
          100: "#f1f5f9",
          200: "#e2e8f0",
          800: "#1e293b",
          900: "#0f172a",
          950: "#020617",
        },
      },
      fontFamily: {
        sans:  ["'DM Sans'", "system-ui", "sans-serif"],
        mono:  ["'JetBrains Mono'", "monospace"],
        display: ["'Cabinet Grotesk'", "'DM Sans'", "sans-serif"],
      },
      animation: {
        "fade-in":     "fadeIn 0.4s ease both",
        "slide-up":    "slideUp 0.35s ease both",
        "pulse-dot":   "pulseDot 1.4s ease-in-out infinite",
        "shimmer":     "shimmer 1.5s linear infinite",
      },
      keyframes: {
        fadeIn:    { from: { opacity: 0 }, to: { opacity: 1 } },
        slideUp:   { from: { opacity: 0, transform: "translateY(12px)" }, to: { opacity: 1, transform: "translateY(0)" } },
        pulseDot:  { "0%,100%": { opacity: 1 }, "50%": { opacity: 0.3 } },
        shimmer:   { from: { backgroundPosition: "-200% 0" }, to: { backgroundPosition: "200% 0" } },
      },
    },
  },
  plugins: [],
};
