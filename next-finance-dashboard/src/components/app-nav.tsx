"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { C } from "@/components/theme";

type Route = {
  href: string;
  path: string;
  label: string;
  kr: string;
};

const ROUTES: Route[] = [
  { href: "/",              path: "/",              label: "Dashboard",    kr: "대시보드" },
  { href: "/assistant",     path: "/assistant",     label: "Assistant",    kr: "어시스턴트" },
  { href: "/sec",           path: "/sec",           label: "SEC 10-K",     kr: "SEC 10-K" },
  { href: "/dart",          path: "/dart",          label: "DART",         kr: "DART" },
  { href: "/dart/license",  path: "/dart/license",  label: "License Lab",  kr: "라이선스 랩" },
  { href: "/annotate",      path: "/annotate",      label: "Annotate",     kr: "어노테이션" },
];

export function AppNav() {
  const pathname = usePathname();

  return (
    <header
      style={{
        display: "flex",
        alignItems: "stretch",
        borderBottom: `1px solid ${C.bd}`,
        background: C.bgCard,
        height: 56,
        position: "sticky",
        top: 0,
        zIndex: 50,
      }}
    >
      {/* Brand */}
      <Link
        href="/"
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "0 20px",
          borderRight: `1px solid ${C.bd}`,
          minWidth: 260,
          textDecoration: "none",
          color: C.text,
        }}
      >
        <div
          style={{
            width: 24,
            height: 24,
            border: `1.5px solid ${C.text}`,
            display: "grid",
            placeItems: "center",
            fontFamily: "var(--font-serif)",
            fontWeight: 700,
            fontSize: 14,
            fontStyle: "italic",
          }}
        >
          §
        </div>
        <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.15 }}>
          <span
            style={{
              fontFamily: "var(--font-serif)",
              fontSize: 15,
              fontWeight: 600,
              letterSpacing: "-0.01em",
            }}
          >
            License Intelligence
          </span>
          <span
            style={{
              fontFamily: "var(--font-sans), Inter, sans-serif",
              fontSize: 10,
              fontWeight: 500,
              color: C.muted,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
              marginTop: 2,
            }}
          >
            SEC · DART · Comparables Workbench
          </span>
        </div>
      </Link>

      {/* Routes */}
      <nav style={{ display: "flex", alignItems: "stretch", padding: "0 4px", overflowX: "auto" }}>
        {ROUTES.map(r => {
          const active =
            r.href === "/" ? pathname === "/" : pathname === r.href || pathname.startsWith(r.href + "/");
          return (
            <Link
              key={r.href}
              href={r.href}
              style={{
                position: "relative",
                padding: "0 14px",
                display: "flex",
                alignItems: "center",
                gap: 8,
                fontSize: 12.5,
                color: active ? C.text : C.text2,
                fontWeight: active ? 600 : 400,
                textDecoration: "none",
                whiteSpace: "nowrap",
              }}
            >
              <span
                style={{
                  fontFamily: "var(--font-jetbrains), monospace",
                  color: C.dim,
                  fontWeight: 400,
                }}
              >
                {r.path}
              </span>
              <span>{r.label}</span>
              <span
                style={{
                  fontFamily: "var(--font-sans), Inter, sans-serif",
                  color: C.muted,
                  fontSize: 11,
                }}
              >
                · {r.kr}
              </span>
              {active && (
                <span
                  style={{
                    position: "absolute",
                    left: 10,
                    right: 10,
                    bottom: -1,
                    height: 2,
                    background: C.accent,
                  }}
                />
              )}
            </Link>
          );
        })}
      </nav>

      {/* Right: search + status */}
      <div
        style={{
          marginLeft: "auto",
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "0 16px",
          borderLeft: `1px solid ${C.bd}`,
          fontSize: 11.5,
          color: C.muted,
        }}
      >
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "3px 10px",
            border: `1px solid ${C.bd}`,
            borderRadius: 999,
            background: C.bgCard,
            fontFamily: "var(--font-jetbrains), monospace",
            fontSize: 10.5,
            color: C.muted,
          }}
        >
          <span
            className="anim-pulse"
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: C.up,
              display: "inline-block",
            }}
          />
          pipeline · running
        </span>
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            padding: "3px 10px",
            border: `1px solid ${C.bd}`,
            borderRadius: 999,
            background: C.bgCard,
            fontFamily: "var(--font-jetbrains), monospace",
            fontSize: 10.5,
          }}
        >
          gemini-1.5-pro
        </span>
      </div>
    </header>
  );
}
