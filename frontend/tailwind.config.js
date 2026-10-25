/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Inter Tight Variable"', "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ['"JetBrains Mono Variable"', "ui-monospace", "Consolas", "monospace"],
      },
      colors: {
        ink: { DEFAULT: "#18212f", soft: "#3b4556", muted: "#6a7385", faint: "#9aa2b1" },
        line: { DEFAULT: "#e4e7ec", strong: "#d3d8e0" },
        canvas: "#f6f7f9",
        brand: { DEFAULT: "#0e7a5c", soft: "#e7f4ef", strong: "#0a5f48" },
        stage: {
          applied: "#3d6fd6", screening: "#7f5bd1", interviewing: "#d97f06", offer: "#0e9a69", closed: "#8f97a6",
        },
        alert: { DEFAULT: "#c2410c", soft: "#fdf0e8" },
        danger: { DEFAULT: "#b42318", soft: "#fdecea" },
      },
      boxShadow: {
        card: "0 1px 2px rgba(16,24,40,.05)",
        pop: "0 12px 32px -8px rgba(16,24,40,.18), 0 2px 6px rgba(16,24,40,.06)",
      },
    },
  },
  plugins: [],
};
