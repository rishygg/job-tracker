/** @type {import('tailwindcss').Config} */
const v = (name) => `rgb(var(--${name}) / <alpha-value>)`;
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Inter Tight Variable"', "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ['"JetBrains Mono Variable"', "ui-monospace", "Consolas", "monospace"],
      },
      colors: {
        ink: { DEFAULT: v("ink"), soft: v("ink-soft"), muted: v("ink-muted"), faint: v("ink-faint") },
        line: { DEFAULT: v("line"), strong: v("line-strong") },
        canvas: v("canvas"),
        surface: v("surface"),
        column: v("column"),
        brand: { DEFAULT: v("brand"), soft: v("brand-soft"), strong: v("brand-strong") },
        alert: { DEFAULT: v("alert"), soft: v("alert-soft") },
        danger: { DEFAULT: v("danger"), soft: v("danger-soft") },
        ok: { DEFAULT: v("ok"), bright: v("ok-bright"), soft: v("ok-soft"), line: v("ok-line") },
        warn: { DEFAULT: v("warn"), strong: v("warn-strong"), soft: v("warn-soft"), line: v("warn-line") },
        info: { DEFAULT: v("info"), bright: v("info-bright"), soft: v("info-soft"), line: v("info-line") },
        violet: { DEFAULT: v("violet"), bright: v("violet-bright"), soft: v("violet-soft"), line: v("violet-line") },
        neutral: { soft: v("neutral-soft") },
        amber: { DEFAULT: "#d97f06" },
        stage: {
          applied: "#3d6fd6", screening: "#7f5bd1", interviewing: "#d97f06", offer: "#0e9a69", closed: "#8f97a6",
        },
      },
      boxShadow: {
        card: "0 1px 2px rgb(var(--shadow) / .05)",
        pop: "0 12px 32px -8px rgb(var(--shadow) / .18), 0 2px 6px rgb(var(--shadow) / .06)",
      },
    },
  },
  plugins: [],
};
