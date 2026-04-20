/**
 * Design System — Courthouse Archive
 *
 * SEC/DART License Intelligence Workbench. Warm paper, deep ink, hairline
 * rules, single configurable accent (default oxblood). All tokens below
 * map 1:1 to the CSS variables declared in app/globals.css so inline
 * React styles and CSS stay in sync.
 */
export const C = {
  // Paper / surfaces
  bg: "#fbf8f3",
  bgCard: "#fefcf8",
  bgCardHover: "#f4efe6",
  bgInput: "#fefcf8",
  bgEl: "#f4efe6",
  bgSec: "#fbf8f3",
  bgGlass: "#fefcf8",

  // Ink
  text: "#1b1f2a",
  text2: "#4a4f5c",
  muted: "#6d7381",
  dim: "#98a1a8",

  // Rules
  bd: "#c8c4b8",
  bdFocus: "#86312a",
  bdSoft: "#e2ddcf",

  // Accent — oxblood
  accent: "#86312a",
  accentSoft: "#efd6c9",
  accentHover: "#a03c33",
  cta: "#86312a",
  ctaSoft: "#efd6c9",

  // Semantic (muted, light-mode friendly)
  up: "#3b6a46",
  upSoft: "#d7e5d4",
  down: "#86312a",
  downSoft: "#efd6c9",
  warn: "#9a6617",
  warnSoft: "#f1e1c5",
  cyan: "#3d577a",
  cyanSoft: "#dde6ee",

  // Extra tonal families (SEC, DART, unified) — used for source badges
  sec: "#3d577a",
  secSoft: "#dde6ee",
  dart: "#3b6a46",
  dartSoft: "#d7e5d4",
  unified: "#3b3d4a",
  unifiedSoft: "#e2e0d8",
} as const;

export const CHART_COLORS = [
  C.accent,
  C.sec,
  C.dart,
  C.warn,
  "#6b4e8a",
  "#4a6b8a",
  "#7a4a3c",
  "#8a7a3c",
];

export const inputStyle: React.CSSProperties = {
  width: "100%",
  marginTop: 4,
  padding: "8px 10px",
  background: C.bgInput,
  border: `1px solid ${C.bd}`,
  borderRadius: 4,
  color: C.text,
  fontSize: 12.5,
  outline: "none",
  fontFamily: "var(--font-sans), Inter, sans-serif",
  transition: "border-color 0.15s ease, box-shadow 0.15s ease",
};

export const selectStyle: React.CSSProperties = {
  ...inputStyle,
  cursor: "pointer",
  appearance: "none",
  backgroundImage:
    "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236d7381' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E\")",
  backgroundRepeat: "no-repeat",
  backgroundPosition: "right 10px center",
  paddingRight: 30,
};

export const tooltipStyle = {
  background: C.bgCard,
  border: `1px solid ${C.bd}`,
  borderRadius: 4,
  fontSize: 12,
  color: C.text,
  boxShadow: "0 4px 16px rgba(40, 30, 20, 0.08)",
  fontFamily: "var(--font-sans), Inter, sans-serif",
};

export const buttonStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 6,
  height: 28,
  padding: "0 12px",
  background: C.bgCard,
  border: `1px solid ${C.bd}`,
  borderRadius: 4,
  color: C.text,
  fontSize: 12,
  fontWeight: 500,
  cursor: "pointer",
  fontFamily: "var(--font-sans), Inter, sans-serif",
  letterSpacing: 0,
  transition: "background-color 0.15s ease, border-color 0.15s ease",
};

export const buttonPrimaryStyle: React.CSSProperties = {
  ...buttonStyle,
  background: C.text,
  border: `1px solid ${C.text}`,
  color: C.bg,
};

export const fmtN = (v: number | null | undefined) =>
  v != null ? Number(v).toLocaleString() : "—";

export const fmtPct = (v: number | string | null | undefined) => {
  const n = Number(v);
  return Number.isNaN(n) || v == null || String(v).trim() === "" ? "—" : `${n.toFixed(2)}%`;
};

export const fmtMoney = (v: number | string | null | undefined, ccy?: string | null) => {
  const n = Number(v);
  if (Number.isNaN(n) || v == null || String(v).trim() === "") return "—";
  const p = ccy || "$";
  if (n >= 1e9) return `${p}${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${p}${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${p}${(n / 1e3).toFixed(0)}K`;
  return `${p}${n.toLocaleString()}`;
};

export const confColor = (v: number) =>
  v >= 0.8 ? C.up : v >= 0.6 ? C.warn : v >= 0.4 ? "#b97e34" : C.accent;
