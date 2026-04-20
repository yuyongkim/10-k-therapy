"use client";

import React from "react";
import { C, confColor } from "@/components/theme";

/* ───────────────────── KPI ───────────────────── */
export function KPI({ label, value, sub, color, trend }: {
  label: string; value: string; sub?: string; color: string; trend?: "up" | "down" | null;
}) {
  return (
    <div
      style={{
        padding: "14px 18px",
        borderRight: `1px solid ${C.bd}`,
        background: C.bgCard,
        minWidth: 0,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span className="upper" style={{ color: C.dim }}>{label}</span>
        {trend && (
          <span style={{ fontSize: 11, color: trend === "up" ? C.up : C.accent, fontWeight: 600 }}>
            {trend === "up" ? "↑" : "↓"}
          </span>
        )}
      </div>
      <div
        style={{
          fontFamily: "var(--font-serif)",
          fontSize: 28,
          fontWeight: 500,
          color,
          letterSpacing: "-0.02em",
          lineHeight: 1.1,
          marginTop: 10,
        }}
      >
        {value}
      </div>
      {sub && (
        <div
          style={{
            marginTop: 6,
            fontSize: 11,
            color: C.muted,
            fontFamily: "var(--font-jetbrains), monospace",
          }}
        >
          {sub}
        </div>
      )}
    </div>
  );
}

/* ───────────────────── Panel (card w/ head) ───────────────────── */
export function Panel({ title, badge, children, className }: {
  title: string; badge?: string; children: React.ReactNode; className?: string;
}) {
  return (
    <section
      className={className}
      style={{
        background: C.bgCard,
        border: `1px solid ${C.bd}`,
        borderRadius: 4,
      }}
    >
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "10px 14px",
          borderBottom: `1px solid ${C.bd}`,
        }}
      >
        <span
          style={{
            fontFamily: "var(--font-serif)",
            fontSize: 13.5,
            fontWeight: 600,
            letterSpacing: "-0.01em",
            color: C.text,
          }}
        >
          {title}
        </span>
        {badge && (
          <span
            style={{
              fontSize: 10.5,
              color: C.accent,
              background: C.accentSoft,
              padding: "2px 8px",
              borderRadius: 2,
              fontFamily: "var(--font-jetbrains), monospace",
              letterSpacing: "0.02em",
            }}
          >
            {badge}
          </span>
        )}
      </header>
      <div style={{ padding: 16 }}>{children}</div>
    </section>
  );
}

/* ───────────────────── MiniCard ───────────────────── */
export function MiniCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        background: C.bgCard,
        border: `1px solid ${C.bd}`,
        borderRadius: 4,
        padding: 14,
      }}
    >
      <div
        className="upper"
        style={{
          color: C.dim,
          padding: "0 0 10px",
          borderBottom: `1px solid ${C.bdSoft}`,
          marginBottom: 10,
        }}
      >
        {title}
      </div>
      {children}
    </div>
  );
}

/* ───────────────────── ConfBar ───────────────────── */
export function ConfBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const clr = confColor(value);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, width: 90 }}>
      <div
        style={{
          flex: 1,
          height: 6,
          background: C.bgEl,
          overflow: "hidden",
          borderRadius: 1,
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${pct}%`,
            background: clr,
            transition: "width 0.4s cubic-bezier(0.4, 0, 0.2, 1)",
          }}
        />
      </div>
      <span
        style={{
          fontSize: 11,
          fontFamily: "var(--font-jetbrains), monospace",
          color: clr,
          minWidth: 24,
          textAlign: "right",
          fontWeight: 600,
        }}
      >
        {pct}
      </span>
    </div>
  );
}

/* ───────────────────── TabBtn ───────────────────── */
export function TabBtn({ active, onClick, children }: {
  active: boolean; onClick: () => void; children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className="transition-colors"
      style={{
        padding: "8px 16px",
        marginBottom: -1,
        background: "transparent",
        border: "none",
        borderBottom: `2px solid ${active ? C.accent : "transparent"}`,
        color: active ? C.text : C.muted,
        fontSize: 13,
        fontWeight: active ? 600 : 400,
        cursor: "pointer",
        fontFamily: "var(--font-sans), Inter, sans-serif",
      }}
    >
      {children}
    </button>
  );
}

/* ───────────────────── FilterField ───────────────────── */
export function FilterField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginTop: 14 }}>
      <label
        style={{
          display: "block",
          fontSize: 10.5,
          color: C.dim,
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          fontWeight: 600,
          marginBottom: 4,
        }}
      >
        {label}
      </label>
      {children}
    </div>
  );
}

/* ───────────────────── DetailBox ───────────────────── */
export function DetailBox({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        background: C.bgCard,
        border: `1px solid ${C.bd}`,
        borderRadius: 4,
      }}
    >
      <div
        style={{
          fontSize: 10.5,
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          color: C.dim,
          padding: "10px 14px",
          borderBottom: `1px solid ${C.bd}`,
          fontFamily: "var(--font-sans), Inter, sans-serif",
        }}
      >
        {title}
      </div>
      <div style={{ padding: 14 }}>{children}</div>
    </div>
  );
}

/* ───────────────────── DRow ───────────────────── */
export function DRow({ label, value, highlight }: {
  label: string; value?: string | null; highlight?: boolean;
}) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        fontSize: 12,
        marginTop: 6,
        gap: 12,
      }}
    >
      <span style={{ color: C.muted }}>{label}</span>
      <span
        style={{
          color: value && value !== "—" && value !== "--" ? (highlight ? C.accent : C.text) : C.dim,
          fontWeight: highlight ? 600 : 500,
          textAlign: "right",
          maxWidth: 200,
          overflow: "hidden",
          textOverflow: "ellipsis",
          fontFamily: "var(--font-jetbrains), monospace",
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {value || "—"}
      </span>
    </div>
  );
}

/* ───────────────────── SourceBadge ───────────────────── */
export function SourceBadge({ source }: { source: string | null }) {
  const s = (source || "").toUpperCase();
  const bg = s === "EDGAR" || s === "SEC" ? C.secSoft : s === "DART" ? C.dartSoft : C.bgEl;
  const fg = s === "EDGAR" || s === "SEC" ? C.sec : s === "DART" ? C.dart : C.muted;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        fontSize: 10.5,
        fontWeight: 600,
        padding: "2px 7px",
        borderRadius: 2,
        background: bg,
        color: fg,
        letterSpacing: "0.02em",
        fontFamily: "var(--font-jetbrains), monospace",
      }}
    >
      <span
        style={{
          display: "inline-block",
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: fg,
        }}
      />
      {s || "—"}
    </span>
  );
}

/* ───────────────────── SourceChip (with accession / rcept) ───────────────────── */
export function SourceChip({
  src,
  code,
  form,
}: {
  src: "sec" | "dart" | "unified" | "lit" | "val";
  code?: string | null;
  form?: string | null;
}) {
  const toneMap: Record<string, { bg: string; fg: string; label: string }> = {
    sec:     { bg: C.secSoft,     fg: C.sec,     label: "SEC" },
    dart:    { bg: C.dartSoft,    fg: C.dart,    label: "DART" },
    unified: { bg: C.unifiedSoft, fg: C.unified, label: "UNIFIED" },
    lit:     { bg: C.warnSoft,    fg: C.warn,    label: "LIT" },
    val:     { bg: C.accentSoft,  fg: C.accent,  label: "VAL" },
  };
  const t = toneMap[src];
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        padding: "1px 7px",
        borderRadius: 2,
        fontSize: 10.5,
        fontFamily: "var(--font-jetbrains), monospace",
        background: t.bg,
        color: t.fg,
        lineHeight: 1.55,
      }}
    >
      <span
        style={{
          display: "inline-block",
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: t.fg,
        }}
      />
      <b style={{ fontWeight: 700 }}>{t.label}</b>
      {form && <span style={{ opacity: 0.7 }}>· {form}</span>}
      {code && <span>· {code}</span>}
    </span>
  );
}

/* ───────────────────── Prov (provenance strip) ───────────────────── */
export function Prov({
  sec,
  dart,
}: {
  sec?: { accession?: string | null; form?: string | null } | null;
  dart?: { rcept_no?: string | null; report?: string | null } | null;
}) {
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 10,
        flexWrap: "wrap",
        fontFamily: "var(--font-jetbrains), monospace",
        fontSize: 10.5,
        color: C.muted,
      }}
    >
      {sec?.accession && <SourceChip src="sec" form={sec.form} code={sec.accession} />}
      {dart?.rcept_no && <SourceChip src="dart" form={dart.report} code={dart.rcept_no} />}
      {!sec?.accession && !dart?.rcept_no && (
        <span style={{ color: C.dim }}>— no provenance —</span>
      )}
    </div>
  );
}

/* ───────────────────── Quote (legal passage) ───────────────────── */
export function Quote({ text, cite }: { text: string; cite?: string }) {
  return (
    <blockquote
      style={{
        fontFamily: "var(--font-serif)",
        fontSize: 14,
        lineHeight: 1.6,
        color: C.text,
        padding: "8px 0 8px 16px",
        borderLeft: `2px solid ${C.accent}`,
        margin: "12px 0",
      }}
    >
      <span dangerouslySetInnerHTML={{ __html: text }} />
      {cite && (
        <span
          style={{
            display: "block",
            marginTop: 6,
            fontFamily: "var(--font-jetbrains), monospace",
            fontSize: 10.5,
            color: C.muted,
            fontStyle: "normal",
          }}
        >
          — {cite}
        </span>
      )}
    </blockquote>
  );
}

/* ───────────────────── Skeleton ───────────────────── */
export function Skeleton({ width, height = 16 }: { width?: number | string; height?: number }) {
  return (
    <div className="skeleton" style={{ width: width || "100%", height, borderRadius: 4 }} />
  );
}

/* ───────────────────── EmptyState ───────────────────── */
export function EmptyState({ message = "No data available" }: { message?: string }) {
  return (
    <div style={{ padding: "56px 0", textAlign: "center", color: C.muted, fontSize: 13 }}>
      <svg
        width="40"
        height="40"
        viewBox="0 0 24 24"
        fill="none"
        stroke={C.dim}
        strokeWidth="1.5"
        style={{ margin: "0 auto 12px", display: "block", opacity: 0.6 }}
      >
        <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
      {message}
    </div>
  );
}

/* ───────────────────── InlineError ───────────────────── */
export function InlineError({ title, message }: { title: string; message: string }) {
  return (
    <div
      style={{
        padding: "14px 16px",
        borderRadius: 4,
        border: `1px solid ${C.accent}`,
        background: C.accentSoft,
        color: C.accentHover,
      }}
    >
      <div
        style={{
          fontSize: 10.5,
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          color: C.accent,
          fontWeight: 600,
        }}
      >
        {title}
      </div>
      <p style={{ marginTop: 6, fontSize: 13, color: C.text, lineHeight: 1.6 }}>{message}</p>
    </div>
  );
}

/* ───────────────────── ProgressBar ───────────────────── */
export function ProgressBar({ label, current, total, sub, color }: {
  label: string; current: number; total: number; sub?: string; color?: string;
}) {
  const pct = total > 0 ? Math.min(100, Math.round((current / total) * 100)) : 0;
  const barColor = color || C.accent;
  const done = pct >= 100;
  return (
    <div
      style={{
        background: C.bgCard,
        border: `1px solid ${done ? C.up : C.bd}`,
        borderRadius: 4,
        padding: "12px 16px",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: C.text2 }}>{label}</span>
        <span
          style={{
            fontSize: 12,
            fontFamily: "var(--font-jetbrains), monospace",
            color: done ? C.up : barColor,
            fontWeight: 600,
          }}
        >
          {done ? "COMPLETE" : `${pct}%`}
        </span>
      </div>
      <div
        style={{
          marginTop: 8,
          height: 4,
          background: C.bgEl,
          overflow: "hidden",
          borderRadius: 1,
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${pct}%`,
            background: done ? C.up : barColor,
            transition: "width 0.6s cubic-bezier(0.4, 0, 0.2, 1)",
          }}
        />
      </div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginTop: 6,
          gap: 12,
          fontSize: 11,
          color: C.muted,
          fontFamily: "var(--font-jetbrains), monospace",
          flexWrap: "wrap",
        }}
      >
        <span>
          {current.toLocaleString()} / {total.toLocaleString()}
        </span>
        {sub && <span>{sub}</span>}
      </div>
    </div>
  );
}

/* ───────────────────── StatPill ───────────────────── */
export function StatPill({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        background: C.bgCard,
        border: `1px solid ${C.bd}`,
        padding: "3px 10px",
        borderRadius: 999,
        fontSize: 11,
      }}
    >
      <span style={{ color: C.muted }}>{label}</span>
      <span
        style={{
          color: color || C.text,
          fontWeight: 600,
          fontFamily: "var(--font-jetbrains), monospace",
        }}
      >
        {value}
      </span>
    </span>
  );
}

/* ───────────────────── HealthStrip ───────────────────── */
export function HealthStrip({ items }: {
  items: {
    label: string;
    value: string;
    tone?: "accent" | "up" | "warn" | "down" | "cyan" | "muted";
    sub?: string;
    labelKr?: string;
  }[];
}) {
  const toneColor = (tone?: "accent" | "up" | "warn" | "down" | "cyan" | "muted") => {
    switch (tone) {
      case "up":     return C.up;
      case "warn":   return C.warn;
      case "down":   return C.accent;
      case "cyan":   return C.sec;
      case "muted":  return C.text;
      case "accent":
      default:       return C.text;
    }
  };

  return (
    <div className="health-strip-grid">
      {items.map((item, idx) => (
        <div
          key={item.label}
          style={{
            padding: "14px 16px",
            borderRight: idx < items.length - 1 ? `1px solid ${C.bd}` : "none",
            minWidth: 0,
            background: C.bgCard,
          }}
        >
          <div
            className="upper"
            style={{ color: C.dim, marginBottom: 8 }}
          >
            {item.label}
            {item.labelKr && <span className="kr" style={{ marginLeft: 6 }}>· {item.labelKr}</span>}
          </div>
          <div
            style={{
              fontFamily: "var(--font-serif)",
              fontSize: 22,
              fontWeight: 500,
              letterSpacing: "-0.01em",
              lineHeight: 1.1,
              color: toneColor(item.tone),
            }}
          >
            {item.value}
            {item.tone === "warn" && (
              <small
                style={{
                  fontFamily: "var(--font-sans), Inter, sans-serif",
                  fontSize: 11,
                  color: C.warn,
                  marginLeft: 6,
                  fontWeight: 500,
                }}
              >
                · review
              </small>
            )}
          </div>
          {item.sub && (
            <div
              style={{
                marginTop: 6,
                fontSize: 11,
                color: C.muted,
                fontFamily: "var(--font-jetbrains), monospace",
              }}
            >
              {item.sub}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

/* ───────────────────── SourceCompareCard ───────────────────── */
export function SourceCompareCard({
  label,
  value,
  sub,
  meta,
  active,
  tone,
  onClick,
}: {
  label: string;
  value: string;
  sub: string;
  meta: string;
  active?: boolean;
  tone?: string;
  onClick?: () => void;
}) {
  const borderColor = active ? tone || C.accent : C.bd;
  return (
    <button
      type="button"
      onClick={onClick}
      className="card-hover transition-colors"
      style={{
        width: "100%",
        textAlign: "left",
        padding: 16,
        borderRadius: 4,
        borderTop: `1px solid ${borderColor}`,
        borderRight: `1px solid ${borderColor}`,
        borderBottom: `1px solid ${borderColor}`,
        borderLeft: `3px solid ${tone || C.accent}`,
        background: active ? C.accentSoft : C.bgCard,
        cursor: "pointer",
        fontFamily: "inherit",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "flex-start" }}>
        <div>
          <div className="upper" style={{ color: C.dim }}>{label}</div>
          <div
            style={{
              marginTop: 8,
              fontFamily: "var(--font-serif)",
              fontSize: 24,
              fontWeight: 500,
              letterSpacing: "-0.02em",
              color: tone || C.text,
            }}
          >
            {value}
          </div>
        </div>
        <span
          style={{
            padding: "2px 8px",
            borderRadius: 2,
            background: active ? C.bgCard : C.bgEl,
            color: tone || C.text2,
            fontSize: 10.5,
            fontWeight: 600,
            fontFamily: "var(--font-jetbrains), monospace",
            border: `1px solid ${C.bd}`,
          }}
        >
          {sub}
        </span>
      </div>
      <div
        style={{
          marginTop: 10,
          fontSize: 11.5,
          color: C.text2,
          lineHeight: 1.55,
        }}
      >
        {meta}
      </div>
    </button>
  );
}

/* ───────────────────── CompareTray ───────────────────── */
export function CompareTray({
  items,
  selectedId,
  onSelect,
  onRemove,
}: {
  items: { id: number; title: string; meta: string; tone?: string }[];
  selectedId?: number | null;
  onSelect: (id: number) => void;
  onRemove: (id: number) => void;
}) {
  if (!items.length) return null;

  return (
    <div
      style={{
        padding: 14,
        background: C.bgCard,
        border: `1px solid ${C.bd}`,
        borderRadius: 4,
        marginBottom: 14,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 12,
          marginBottom: 10,
        }}
      >
        <div
          style={{
            fontFamily: "var(--font-serif)",
            fontSize: 13,
            fontWeight: 600,
            color: C.text,
          }}
        >
          Compare tray <span className="kr" style={{ marginLeft: 4 }}>· 비교 트레이</span>
        </div>
        <div style={{ fontSize: 11, color: C.muted }}>
          Pin up to 3 · <span className="kr">최대 3건</span>
        </div>
      </div>
      <div className="compare-tray-grid">
        {items.map((item) => {
          const active = selectedId === item.id;
          return (
            <div
              key={item.id}
              style={{
                borderRadius: 4,
                borderTop: `1px solid ${active ? item.tone || C.accent : C.bd}`,
                borderRight: `1px solid ${active ? item.tone || C.accent : C.bd}`,
                borderBottom: `1px solid ${active ? item.tone || C.accent : C.bd}`,
                borderLeft: `3px solid ${item.tone || C.accent}`,
                background: active ? C.accentSoft : C.bgCard,
                padding: 12,
              }}
            >
              <button
                type="button"
                onClick={() => onSelect(item.id)}
                style={{ all: "unset", cursor: "pointer", display: "block", width: "100%" }}
              >
                <div
                  style={{
                    fontFamily: "var(--font-serif)",
                    fontSize: 13,
                    fontWeight: 600,
                    color: C.text,
                  }}
                >
                  {item.title}
                </div>
                <div
                  style={{
                    marginTop: 5,
                    fontSize: 11,
                    color: C.text2,
                    lineHeight: 1.5,
                    fontFamily: "var(--font-jetbrains), monospace",
                  }}
                >
                  {item.meta}
                </div>
              </button>
              <button
                type="button"
                onClick={() => onRemove(item.id)}
                style={{
                  marginTop: 10,
                  padding: "3px 8px",
                  borderRadius: 2,
                  border: `1px solid ${C.bd}`,
                  background: "transparent",
                  color: C.muted,
                  fontSize: 11,
                  cursor: "pointer",
                  fontFamily: "inherit",
                }}
              >
                Remove
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ───────────────────── EvidenceCard ───────────────────── */
export function EvidenceCard({
  title,
  meta,
  snippet,
  onClick,
}: {
  title: string;
  meta?: string;
  snippet?: string;
  onClick?: () => void;
}) {
  const inner = (
    <>
      <div
        style={{
          fontFamily: "var(--font-serif)",
          fontSize: 13,
          fontWeight: 500,
          color: C.text,
          marginBottom: 2,
        }}
      >
        {title}
      </div>
      {meta && (
        <div
          style={{
            fontFamily: "var(--font-jetbrains), monospace",
            fontSize: 10.5,
            color: C.muted,
            marginBottom: 6,
          }}
        >
          {meta}
        </div>
      )}
      {snippet && (
        <div
          style={{
            fontFamily: "var(--font-serif)",
            fontSize: 12,
            color: C.text2,
            fontStyle: "italic",
            lineHeight: 1.5,
          }}
        >
          {snippet}
        </div>
      )}
    </>
  );
  return onClick ? (
    <button
      type="button"
      onClick={onClick}
      style={{
        all: "unset",
        cursor: "pointer",
        display: "block",
        border: `1px solid ${C.bd}`,
        background: C.bgCard,
        padding: "10px 12px",
        borderRadius: 4,
        fontSize: 11.5,
        marginBottom: 8,
        width: "100%",
      }}
    >
      {inner}
    </button>
  ) : (
    <div
      style={{
        border: `1px solid ${C.bd}`,
        background: C.bgCard,
        padding: "10px 12px",
        borderRadius: 4,
        fontSize: 11.5,
        marginBottom: 8,
      }}
    >
      {inner}
    </div>
  );
}

/* ───────────────────── Segmented (seg) ───────────────────── */
export function Seg<T extends string>({
  value,
  onChange,
  options,
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string }[];
}) {
  return (
    <div
      style={{
        display: "inline-flex",
        border: `1px solid ${C.bd}`,
        background: C.bgEl,
        borderRadius: 4,
        padding: 2,
      }}
    >
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          style={{
            border: 0,
            background: value === o.value ? C.bgCard : "transparent",
            padding: "3px 10px",
            fontSize: 11.5,
            color: value === o.value ? C.text : C.muted,
            cursor: "pointer",
            borderRadius: 2,
            boxShadow: value === o.value ? `0 0 0 1px ${C.bd}` : "none",
            fontFamily: "inherit",
            fontWeight: value === o.value ? 600 : 400,
          }}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/* ───────────────────── LayoutPicker ───────────────────── */
export type DashVariation = "A" | "B" | "C" | "D";
export function LayoutPicker({
  value,
  onChange,
}: {
  value: DashVariation;
  onChange: (v: DashVariation) => void;
}) {
  const opts: { v: DashVariation; k: string; label: string; kr: string }[] = [
    { v: "A", k: "1", label: "Evidence Ledger",  kr: "증거원장" },
    { v: "B", k: "2", label: "Comparables Grid", kr: "비교표" },
    { v: "C", k: "3", label: "Split Provenance", kr: "이원 대조" },
    { v: "D", k: "4", label: "Assistant-first",  kr: "어시스턴트" },
  ];
  return (
    <div
      role="tablist"
      aria-label="Dashboard variation"
      style={{
        display: "flex",
        gap: 6,
        padding: 6,
        border: `1px solid ${C.bd}`,
        background: C.bgEl,
        borderRadius: 6,
      }}
    >
      {opts.map((o) => {
        const active = value === o.v;
        return (
          <button
            key={o.v}
            onClick={() => onChange(o.v)}
            className="transition-colors"
            style={{
              padding: "6px 10px",
              borderRadius: 4,
              cursor: "pointer",
              fontSize: 11.5,
              color: active ? C.text : C.muted,
              display: "flex",
              alignItems: "center",
              gap: 6,
              border: 0,
              background: active ? C.bgCard : "transparent",
              boxShadow: active ? `0 0 0 1px ${C.bd}` : "none",
              fontFamily: "inherit",
              fontWeight: active ? 600 : 400,
            }}
          >
            <span
              style={{
                fontFamily: "var(--font-jetbrains), monospace",
                fontSize: 10,
                color: active ? C.text : C.dim,
                border: `1px solid ${active ? C.text : C.bd}`,
                padding: "0 4px",
                borderRadius: 2,
              }}
            >
              {o.k}
            </span>
            <span>{o.label}</span>
            <span className="kr">· {o.kr}</span>
          </button>
        );
      })}
    </div>
  );
}

/* ───────────────────── Tweaks ───────────────────── */
export type TweaksState = {
  accentHue: number;
  density: "compact" | "default" | "comfy";
  variation: DashVariation;
};

export const ACCENT_PRESETS = [
  { name: "Oxblood", kr: "적갈",  hue: 25 },
  { name: "Ink",     kr: "먹",    hue: 250 },
  { name: "Moss",    kr: "이끼",  hue: 150 },
  { name: "Ochre",   kr: "황토",  hue: 75 },
  { name: "Plum",    kr: "자두",  hue: 310 },
];

export function Tweaks({
  open,
  onClose,
  state,
  set,
}: {
  open: boolean;
  onClose: () => void;
  state: TweaksState;
  set: <K extends keyof TweaksState>(key: K, value: TweaksState[K]) => void;
}) {
  if (!open) return null;
  const current = ACCENT_PRESETS.find((p) => p.hue === state.accentHue)?.name || "Custom";
  return (
    <div
      style={{
        position: "fixed",
        right: 20,
        bottom: 20,
        width: 300,
        background: C.bgCard,
        border: `1px solid ${C.bd}`,
        borderRadius: 4,
        boxShadow: "0 16px 48px rgba(40, 30, 20, 0.12)",
        zIndex: 100,
        fontFamily: "var(--font-sans), Inter, sans-serif",
      }}
    >
      <div
        style={{
          padding: "10px 14px",
          display: "flex",
          alignItems: "center",
          gap: 8,
          borderBottom: `1px solid ${C.bd}`,
        }}
      >
        <span
          style={{
            fontFamily: "var(--font-serif)",
            fontSize: 13,
            fontWeight: 600,
            letterSpacing: "-0.01em",
          }}
        >
          Tweaks <span className="kr">· 디자인 조정</span>
        </span>
        <button
          onClick={onClose}
          style={{
            marginLeft: "auto",
            cursor: "pointer",
            color: C.muted,
            background: "none",
            border: "none",
            fontSize: 14,
            padding: 4,
          }}
          aria-label="Close tweaks"
        >
          ✕
        </button>
      </div>
      <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 14 }}>
        <div>
          <label
            style={{
              display: "block",
              fontSize: 10.5,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: C.dim,
              fontWeight: 600,
              marginBottom: 6,
            }}
          >
            Accent · <span className="kr">강조색</span>
          </label>
          <div style={{ display: "flex", gap: 6 }}>
            {ACCENT_PRESETS.map((p) => (
              <button
                key={p.hue}
                onClick={() => set("accentHue", p.hue)}
                style={{
                  width: 26,
                  height: 26,
                  borderRadius: "50%",
                  cursor: "pointer",
                  border: `2px solid ${C.bgCard}`,
                  boxShadow: `0 0 0 ${state.accentHue === p.hue ? 2 : 1}px ${state.accentHue === p.hue ? C.text : C.bd}`,
                  background: `oklch(45% 0.14 ${p.hue})`,
                  padding: 0,
                }}
                title={`${p.name} · ${p.kr}`}
              />
            ))}
          </div>
          <div style={{ fontSize: 11, color: C.dim, marginTop: 6 }}>{current}</div>
        </div>
        <div>
          <label
            style={{
              display: "block",
              fontSize: 10.5,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: C.dim,
              fontWeight: 600,
              marginBottom: 6,
            }}
          >
            Density · <span className="kr">밀도</span>
          </label>
          <Seg
            value={state.density}
            onChange={(v) => set("density", v)}
            options={[
              { value: "compact", label: "Compact" },
              { value: "default", label: "Default" },
              { value: "comfy",   label: "Comfy" },
            ]}
          />
        </div>
        <div>
          <label
            style={{
              display: "block",
              fontSize: 10.5,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: C.dim,
              fontWeight: 600,
              marginBottom: 6,
            }}
          >
            Dashboard · <span className="kr">대시보드 변형</span>
          </label>
          <Seg
            value={state.variation}
            onChange={(v) => set("variation", v)}
            options={[
              { value: "A", label: "A · Ledger" },
              { value: "B", label: "B · Grid" },
              { value: "C", label: "C · Split" },
              { value: "D", label: "D · Chat" },
            ]}
          />
        </div>
        <div
          style={{
            fontSize: 11,
            color: C.dim,
            borderTop: `1px solid ${C.bdSoft}`,
            paddingTop: 10,
            lineHeight: 1.5,
          }}
        >
          Keyboard · <span style={{ fontFamily: "var(--font-jetbrains), monospace" }}>1–4</span> cycle variations
        </div>
      </div>
    </div>
  );
}

/* ───────────────────── TweaksHost (controller) ───────────────────── */
const TWEAKS_KEY = "sec-courthouse-tweaks-v1";

export function useTweaks(): {
  state: TweaksState;
  set: <K extends keyof TweaksState>(key: K, value: TweaksState[K]) => void;
  open: boolean;
  setOpen: (b: boolean) => void;
} {
  const [state, setState] = React.useState<TweaksState>({
    accentHue: 25,
    density: "default",
    variation: "A",
  });
  const [open, setOpen] = React.useState(false);

  React.useEffect(() => {
    try {
      const raw = localStorage.getItem(TWEAKS_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as Partial<TweaksState>;
        setState((s) => ({ ...s, ...parsed }));
      }
    } catch {}
  }, []);

  React.useEffect(() => {
    try {
      localStorage.setItem(TWEAKS_KEY, JSON.stringify(state));
    } catch {}
    const root = document.documentElement;
    root.style.setProperty("--accent-hue", String(state.accentHue));
    root.classList.remove("density-compact", "density-comfy");
    if (state.density === "compact") root.classList.add("density-compact");
    if (state.density === "comfy")   root.classList.add("density-comfy");
  }, [state]);

  React.useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && /INPUT|TEXTAREA/.test(target.tagName)) return;
      if (e.key === "1") setState((s) => ({ ...s, variation: "A" }));
      if (e.key === "2") setState((s) => ({ ...s, variation: "B" }));
      if (e.key === "3") setState((s) => ({ ...s, variation: "C" }));
      if (e.key === "4") setState((s) => ({ ...s, variation: "D" }));
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);

  const set = <K extends keyof TweaksState>(key: K, value: TweaksState[K]) =>
    setState((s) => ({ ...s, [key]: value }));

  return { state, set, open, setOpen };
}
