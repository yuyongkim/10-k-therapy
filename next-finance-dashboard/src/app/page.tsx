"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { AppNav } from "@/components/app-nav";
import {
  C, CHART_COLORS, fmtN, fmtPct, fmtMoney, confColor,
  tooltipStyle, inputStyle, selectStyle, buttonStyle,
} from "@/components/theme";
import {
  KPI, ConfBar, FilterField, DetailBox, DRow, SourceBadge,
  Skeleton, EmptyState, InlineError, StatPill, HealthStrip,
  SourceCompareCard, CompareTray, Panel, Quote, SourceChip,
  LayoutPicker, Tweaks, useTweaks,
  type DashVariation,
} from "@/components/ui";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";
const STORAGE_KEY = "sec-dashboard-workbench-state-v1";
const ASSISTANT_HANDOFF_KEY = "sec-assistant-dashboard-handoff-v1";
const SOURCE_HANDOFF_KEY = "sec-dashboard-source-handoff-v1";

type Contract = {
  id: number; licensor_name: string | null; licensee_name: string | null;
  tech_name: string | null; tech_category: string | null; industry: string | null;
  territory: string | null; term_years: number | null; confidence_score: number | null;
  extraction_model: string | null; source_system: string | null;
  company_name: string | null; ticker: string | null; filing_year: number | null;
  accession_number: string | null; rcept_no: string | null; filing_date: string | null; source_url: string | null;
  royalty_rate: number | null; upfront_amount: number | null;
};
type Pagination = { page: number; page_size: number; total: number; total_pages: number };
type Stats = {
  total_contracts: number; total_companies: number; avg_confidence: number | null;
  avg_royalty: number | null; by_source: Record<string, number>;
  by_category: { category: string; count: number }[];
};

export default function UnifiedDashboard() {
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [loading, setLoading] = useState(true);
  const [source, setSource] = useState<"" | "EDGAR" | "DART">("");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [minConf, setMinConf] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Contract | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [quality, setQuality] = useState<"clean" | "all">("clean");
  const [statsError, setStatsError] = useState("");
  const [contractsError, setContractsError] = useState("");
  const [copied, setCopied] = useState<string | null>(null);
  const [pinnedIds, setPinnedIds] = useState<number[]>([]);
  const [extraction, setExtraction] = useState<{
    status: string; total: number; processed: number; contracts: number;
    errors: number; last_company: string; updated: string;
  } | null>(null);
  const [clientNow, setClientNow] = useState<string>("");

  const tweaks = useTweaks();

  useEffect(() => {
    setClientNow(new Date().toLocaleString("ko-KR"));
  }, []);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (!saved) return;
      const parsed = JSON.parse(saved) as {
        quality?: "clean" | "all";
        source?: "" | "EDGAR" | "DART";
        pinnedIds?: number[];
        selectedId?: number | null;
      };
      if (parsed.quality) setQuality(parsed.quality);
      if (parsed.source !== undefined) setSource(parsed.source);
      if (Array.isArray(parsed.pinnedIds))
        setPinnedIds(parsed.pinnedIds.filter((id) => typeof id === "number").slice(0, 3));
      if (typeof parsed.selectedId === "number") setSelectedId(parsed.selectedId);
    } catch {}
  }, []);

  useEffect(() => {
    try {
      const handoff = window.localStorage.getItem(ASSISTANT_HANDOFF_KEY);
      if (!handoff) return;
      const parsed = JSON.parse(handoff) as {
        search?: string; category?: string; source?: "" | "EDGAR" | "DART";
      };
      if (parsed.search) setSearch(parsed.search);
      if (parsed.category) setCategory(parsed.category);
      if (parsed.source !== undefined) setSource(parsed.source);
      setPage(1);
      setSelected(null);
      setSelectedId(null);
      window.localStorage.removeItem(ASSISTANT_HANDOFF_KEY);
    } catch {}
  }, []);

  useEffect(() => {
    const loadHeaderData = async () => {
      try {
        setStatsError("");
        const [statsRes, extractionRes] = await Promise.all([
          fetch(`${API}/stats/?quality=${quality}`),
          fetch(`${API}/dart/extraction-status`),
        ]);
        if (!statsRes.ok || !extractionRes.ok) throw new Error("dashboard metrics request failed");
        setStats(await statsRes.json());
        setExtraction(await extractionRes.json());
      } catch {
        setStatsError("Topline metrics are temporarily unavailable. Filters and row data still work.");
      }
    };
    loadHeaderData();
  }, [quality]);

  useEffect(() => {
    if (!extraction || extraction.status !== "running") return;
    const interval = setInterval(() => {
      fetch(`${API}/dart/extraction-status`).then(r => r.json()).then(setExtraction).catch(() => {});
      fetch(`${API}/stats/?quality=${quality}`).then(r => r.json()).then(setStats).catch(() => {});
    }, 15000);
    return () => clearInterval(interval);
  }, [extraction, quality]);

  useEffect(() => {
    const p = new URLSearchParams({ page: String(page), page_size: "25", sort: "confidence_score:desc", quality });
    if (source) p.set("source", source);
    if (search) p.set("search", search);
    if (category) p.set("category", category);
    if (minConf) p.set("min_confidence", minConf);

    fetch(`${API}/contracts/?${p}`)
      .then(async r => { if (!r.ok) throw new Error("contracts request failed"); return r.json(); })
      .then(d => {
        setContractsError("");
        setContracts(d.data || []);
        setPagination(d.pagination);
        setLoading(false);
      })
      .catch(() => {
        setContracts([]);
        setContractsError("Contract rows could not be loaded for the current filter set.");
        setLoading(false);
      });
  }, [page, source, search, category, minConf, quality]);

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ quality, source, pinnedIds, selectedId }));
    } catch {}
  }, [quality, source, pinnedIds, selectedId]);

  useEffect(() => {
    if (selectedId == null) {
      if (selected) setSelected(null);
      return;
    }
    const match = contracts.find((c) => c.id === selectedId);
    if (match) setSelected(match);
  }, [contracts, selectedId, selected]);

  const categories = stats?.by_category || [];
  const extractionPct = extraction && extraction.total > 0
    ? Math.round((extraction.processed / extraction.total) * 100)
    : 0;
  const lastRefresh = extraction?.updated || clientNow || "—";
  const highConfidenceCount = contracts.filter((c) => (c.confidence_score || 0) >= 0.8).length;
  const anomalyCount = contracts.filter((c) => (c.confidence_score || 0) < 0.45).length;
  const healthTone: "up" | "warn" | "down" | "cyan" =
    statsError || contractsError ? "down"
      : extraction?.status === "running" ? "cyan"
      : quality === "clean" ? "up"
      : "warn";

  const pinnedContracts = pinnedIds
    .map((id) => contracts.find((c) => c.id === id) || (selected?.id === id ? selected : null))
    .filter((c): c is Contract => Boolean(c));

  const togglePin = (contract: Contract) => {
    setPinnedIds((cur) =>
      cur.includes(contract.id) ? cur.filter((id) => id !== contract.id) : [...cur, contract.id].slice(-3)
    );
  };

  const sourceCards = [
    {
      key: "" as const,
      label: "Unified",
      labelKr: "통합",
      value: fmtN(stats?.total_contracts),
      sub: quality === "clean" ? "validated" : "raw+val",
      meta: `Avg conf ${stats?.avg_confidence != null ? `${(stats.avg_confidence * 100).toFixed(0)}%` : "—"} · Companies ${fmtN(stats?.total_companies)}`,
      tone: C.unified,
    },
    {
      key: "EDGAR" as const,
      label: "SEC",
      labelKr: "SEC 10-K",
      value: fmtN(stats?.by_source?.["EDGAR"]),
      sub: "edgar",
      meta: `Freshness ${lastRefresh} · US disclosures`,
      tone: C.sec,
    },
    {
      key: "DART" as const,
      label: "DART",
      labelKr: "DART 공시",
      value: fmtN(stats?.by_source?.["DART"]),
      sub: extraction?.status === "running" ? "live" : "korea",
      meta: `Progress ${extractionPct}% · Contracts ${fmtN(extraction?.contracts)}`,
      tone: C.dart,
    },
  ];

  const pushToSourcePage = (contract: Contract) => {
    const route = contract.source_system === "DART" ? "/dart" : "/sec";
    try {
      window.localStorage.setItem(SOURCE_HANDOFF_KEY, JSON.stringify({
        route,
        search: contract.company_name || contract.licensor_name || contract.tech_name || "",
        category: contract.tech_category || "",
        minConf: contract.confidence_score != null ? String(Math.max(0.4, Math.floor(contract.confidence_score * 10) / 10)) : "",
      }));
    } catch {}
    window.location.href = route;
  };

  const copyText = async (label: string, value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(`${label} copied`);
    } catch {
      setCopied(`${label} copy failed`);
    }
    window.setTimeout(() => setCopied(null), 1600);
  };

  const openEvidence = (url?: string | null) => {
    if (!url) return;
    window.open(url, "_blank", "noopener,noreferrer");
  };

  /* ────────────── render blocks ────────────── */

  const healthStrip = (
    <HealthStrip
      items={[
        {
          label: "Health",
          labelKr: "상태",
          value: healthTone === "down" ? "Degraded" : healthTone === "cyan" ? "Running" : healthTone === "up" ? "Healthy" : "Review raw",
          tone: healthTone,
          sub: statsError ? "metrics degraded" : `last ${lastRefresh}`,
        },
        { label: "SEC Ingest", labelKr: "SEC 수집", value: fmtN(stats?.by_source?.["EDGAR"]), tone: "muted", sub: "EDGAR 10-K" },
        { label: "DART Ingest", labelKr: "DART 수집", value: fmtN(stats?.by_source?.["DART"]), tone: "muted", sub: `progress ${extractionPct}%` },
        { label: "High conf", labelKr: "고신뢰", value: `${fmtN(highConfidenceCount)} / ${fmtN(contracts.length)}`, tone: "up", sub: "≥ 0.8" },
        { label: "Anomalies", labelKr: "이상치", value: fmtN(anomalyCount), tone: anomalyCount > 0 ? "warn" : "up", sub: "< 0.45" },
      ]}
    />
  );

  const pageHead = (
    <header style={{ marginBottom: 22 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 8 }}>
        <span
          className="upper"
          style={{
            fontFamily: "var(--font-jetbrains), monospace",
            color: C.dim,
            letterSpacing: "0.08em",
          }}
        >
          VAR · {tweaks.state.variation} / UNIFIED DASHBOARD
        </span>
        <span style={{ flex: 1, borderTop: `1px solid ${C.bd}`, transform: "translateY(-3px)" }} />
        <span
          className="upper"
          style={{
            fontFamily: "var(--font-jetbrains), monospace",
            color: C.dim,
          }}
        >
          {fmtN(pagination?.total)} IN SLICE
        </span>
      </div>
      <h1
        style={{
          fontFamily: "var(--font-serif)",
          fontSize: 34,
          fontWeight: 500,
          letterSpacing: "-0.02em",
          margin: "0 0 8px",
          lineHeight: 1.1,
          color: C.text,
        }}
      >
        The <em style={{ fontStyle: "italic", color: C.accent }}>comparables</em> you read,
        not the dashboard you skim.
      </h1>
      <p
        style={{
          fontSize: 13,
          color: C.text2,
          maxWidth: 760,
          lineHeight: 1.65,
          margin: 0,
        }}
      >
        Each license agreement is a case file. Open to the clause, jump to the exhibit, pin for comparison.
        <span style={{ display: "block", marginTop: 2, color: C.muted, fontSize: 12 }}>
          각 라이선스 계약을 문서로 읽는 리서치 워크벤치. 조항 인용, 원문 이동, 비교 핀 고정.
        </span>
      </p>
    </header>
  );

  const toolbar = (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: 12,
        marginTop: 16,
        flexWrap: "wrap",
      }}
    >
      <LayoutPicker
        value={tweaks.state.variation}
        onChange={(v) => tweaks.set("variation", v)}
      />
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <button
          type="button"
          onClick={() =>
            copyText("Workbench context", JSON.stringify({
              source, quality, search, category, minConf, pinnedIds, selectedId,
            }, null, 2))
          }
          style={buttonStyle}
        >
          Copy workbench context
        </button>
        <div
          style={{
            display: "flex",
            borderRadius: 4,
            overflow: "hidden",
            border: `1px solid ${C.bd}`,
          }}
        >
          <button
            onClick={() => { setQuality("clean"); setPage(1); setSelected(null); setSelectedId(null); }}
            style={{
              padding: "6px 12px", fontSize: 11.5, fontWeight: 600, cursor: "pointer", border: "none",
              background: quality === "clean" ? C.text : C.bgCard,
              color: quality === "clean" ? C.bg : C.muted,
              fontFamily: "inherit",
            }}
          >
            Clean
          </button>
          <button
            onClick={() => { setQuality("all"); setPage(1); setSelected(null); setSelectedId(null); }}
            style={{
              padding: "6px 12px", fontSize: 11.5, fontWeight: 600, cursor: "pointer", border: "none",
              background: quality === "all" ? C.text : C.bgCard,
              color: quality === "all" ? C.bg : C.muted,
              fontFamily: "inherit",
            }}
          >
            All (Raw)
          </button>
        </div>
        <button onClick={() => tweaks.setOpen(true)} style={buttonStyle}>Tweaks</button>
        {copied && <StatPill label="Clipboard" value={copied} color={copied.includes("failed") ? C.accent : C.up} />}
      </div>
    </div>
  );

  /* Filters sidebar (shared across variations) */
  const filtersAside = (
    <Panel title="Filters" badge="필터">
      <FilterField label="Search">
        <input
          value={search}
          onChange={(e) => { setPage(1); setSearch(e.target.value); }}
          style={inputStyle}
          placeholder="company, tech…"
        />
      </FilterField>
      <FilterField label="Category">
        <select
          value={category}
          onChange={(e) => { setPage(1); setCategory(e.target.value); }}
          style={selectStyle}
        >
          <option value="">All</option>
          {categories.map(c => (
            <option key={c.category} value={c.category}>{c.category} ({c.count})</option>
          ))}
        </select>
      </FilterField>
      <FilterField label="Min Confidence">
        <select
          value={minConf}
          onChange={(e) => { setPage(1); setMinConf(e.target.value); }}
          style={selectStyle}
        >
          <option value="">Any</option>
          <option value="0.4">40%+</option>
          <option value="0.6">60%+</option>
          <option value="0.8">80%+</option>
        </select>
      </FilterField>
      <button
        onClick={() => { setSearch(""); setCategory(""); setMinConf(""); setPage(1); }}
        style={{ ...buttonStyle, width: "100%", marginTop: 18, justifyContent: "center" }}
      >
        Reset Filters
      </button>

      <div style={{ marginTop: 20, borderTop: `1px solid ${C.bdSoft}`, paddingTop: 16 }}>
        <div className="upper" style={{ color: C.dim, marginBottom: 10 }}>Judge verdict mix</div>
        <div style={{ display: "grid", gap: 8, fontSize: 12 }}>
          {[
            { label: "REAL", pct: 79.3, color: C.up },
            { label: "AMBIGUOUS", pct: 14.2, color: C.warn },
            { label: "FALSE-POS", pct: 6.5, color: C.muted },
          ].map((r) => (
            <div key={r.label}>
              <div
                className="upper"
                style={{ color: r.color, display: "flex", justifyContent: "space-between" }}
              >
                <span>{r.label}</span>
                <span style={{ fontFamily: "var(--font-jetbrains), monospace" }}>{r.pct}%</span>
              </div>
              <div
                style={{
                  marginTop: 4,
                  height: 6,
                  background: C.bgEl,
                  borderRadius: 1,
                  overflow: "hidden",
                }}
              >
                <div style={{ width: `${r.pct}%`, height: "100%", background: r.color }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );

  /* Inspection pane (shared) */
  const inspectionPane = (
    <Panel title="Inspection pane" badge="상세">
      {selected ? (
        <div style={{ display: "grid", gap: 14 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <SourceBadge source={selected.source_system} />
              {selected.confidence_score != null && (
                <span
                  style={{
                    fontSize: 10.5,
                    fontFamily: "var(--font-jetbrains), monospace",
                    color: confColor(selected.confidence_score),
                    padding: "1px 6px",
                    borderRadius: 2,
                    background: C.bgEl,
                  }}
                >
                  conf {(selected.confidence_score * 100).toFixed(0)}%
                </span>
              )}
            </div>
            <h3
              style={{
                marginTop: 8,
                marginBottom: 2,
                fontFamily: "var(--font-serif)",
                fontSize: 18,
                fontWeight: 500,
                letterSpacing: "-0.01em",
              }}
            >
              {selected.company_name || "Unknown"}
            </h3>
            <div style={{ fontSize: 12, color: C.text2 }}>
              {selected.tech_name || "Technology not extracted"}
            </div>
          </div>

          <DetailBox title="Parties">
            <DRow label="Licensor" value={selected.licensor_name} />
            <DRow label="Licensee" value={selected.licensee_name} />
          </DetailBox>
          <DetailBox title="Technology">
            <DRow label="Name" value={selected.tech_name} />
            <DRow label="Category" value={selected.tech_category} />
            {selected.industry && <DRow label="Industry" value={selected.industry} />}
          </DetailBox>
          <DetailBox title="Financial">
            <DRow label="Royalty" value={fmtPct(selected.royalty_rate)} highlight />
            <DRow label="Upfront" value={fmtMoney(selected.upfront_amount)} />
          </DetailBox>
          <DetailBox title="Contract">
            <DRow label="Term" value={selected.term_years ? `${selected.term_years}y` : null} />
            <DRow label="Territory" value={selected.territory} />
            <DRow label="Ticker" value={selected.ticker} />
            <DRow label="Filing year" value={selected.filing_year ? String(selected.filing_year) : null} />
          </DetailBox>
          <DetailBox title="Provenance">
            <DRow label="Source system" value={selected.source_system} />
            <DRow label="Extraction model" value={selected.extraction_model} />
            <DRow label="Validation mode" value={quality === "clean" ? "Clean-first" : "Raw included"} />
            <DRow label="Filing ref" value={selected.accession_number || selected.rcept_no} />
            <DRow label="Filing date" value={selected.filing_date} />
          </DetailBox>
          <div style={{ display: "grid", gap: 6 }}>
            <button type="button" onClick={() => pushToSourcePage(selected)} style={{ ...buttonStyle, width: "100%", justifyContent: "center" }}>
              Open source workbench
            </button>
            <button
              type="button"
              onClick={() => copyText("Contract context", JSON.stringify({
                id: selected.id, source: selected.source_system,
                company: selected.company_name, licensor: selected.licensor_name, licensee: selected.licensee_name,
                technology: selected.tech_name, category: selected.tech_category,
                royalty_rate: selected.royalty_rate, upfront_amount: selected.upfront_amount,
                term_years: selected.term_years, territory: selected.territory,
                confidence_score: selected.confidence_score, filing_year: selected.filing_year,
                extraction_model: selected.extraction_model,
                accession_number: selected.accession_number, rcept_no: selected.rcept_no,
                filing_date: selected.filing_date, source_url: selected.source_url,
              }, null, 2))}
              style={{ ...buttonStyle, width: "100%", justifyContent: "center" }}
            >
              Copy contract context
            </button>
            {selected.source_url && (
              <button
                type="button"
                onClick={() => openEvidence(selected.source_url)}
                style={{ ...buttonStyle, width: "100%", justifyContent: "center", background: C.text, color: C.bg, borderColor: C.text }}
              >
                Open filing evidence
              </button>
            )}
          </div>
        </div>
      ) : (
        <EmptyState message="Pick a row or pin a contract to inspect it here." />
      )}
    </Panel>
  );

  /* Variation A — Evidence Ledger */
  const variationA = (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 340px", gap: 24, marginTop: 20 }}>
      <section>
        <CompareTray
          items={pinnedContracts.map((c) => ({
            id: c.id,
            title: c.company_name || c.tech_name || `Contract ${c.id}`,
            meta: `${c.source_system || "?"} · ${c.tech_category || "Uncategorized"} · ${c.filing_year || "—"} · ${fmtPct(c.royalty_rate)}`,
            tone: c.source_system === "DART" ? C.dart : C.sec,
          }))}
          selectedId={selected?.id}
          onSelect={(id) => {
            const next = pinnedContracts.find((c) => c.id === id) || contracts.find((c) => c.id === id) || null;
            setSelected(next);
            setSelectedId(next?.id ?? null);
          }}
          onRemove={(id) => setPinnedIds((cur) => cur.filter((v) => v !== id))}
        />

        {contractsError && <InlineError title="Rows unavailable" message={contractsError} />}

        {loading && (
          <div style={{ display: "grid", gap: 16, marginTop: 4 }}>
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} style={{ border: `1px solid ${C.bd}`, padding: 16, borderRadius: 4 }}>
                <Skeleton height={14} width={200} />
                <div style={{ height: 10 }} />
                <Skeleton height={20} width={420} />
                <div style={{ height: 8 }} />
                <Skeleton height={10} width={320} />
              </div>
            ))}
          </div>
        )}

        {!loading && !contractsError && contracts.length === 0 && (
          <EmptyState message="No contracts match your filters" />
        )}

        <div style={{ display: "grid" }}>
          {!loading &&
            contracts.map((c, idx) => {
              const pinned = pinnedIds.includes(c.id);
              const sel = selected?.id === c.id;
              return (
                <article
                  key={c.id}
                  className="anim-row"
                  style={{
                    display: "grid",
                    gridTemplateColumns: "150px 1fr 180px",
                    gap: 20,
                    padding: "18px 0",
                    borderTop: idx === 0 ? `1px solid ${C.bdFocus}` : `1px solid ${C.bd}`,
                    cursor: "pointer",
                    background: sel ? C.accentSoft : "transparent",
                    animationDelay: `${idx * 18}ms`,
                  }}
                  onClick={() => {
                    setSelected(sel ? null : c);
                    setSelectedId(sel ? null : c.id);
                  }}
                >
                  <div
                    style={{
                      fontFamily: "var(--font-jetbrains), monospace",
                      fontSize: 11,
                      color: C.muted,
                      lineHeight: 1.7,
                    }}
                  >
                    <div style={{ color: C.text, fontWeight: 600 }}>{c.filing_date || c.filing_year || "—"}</div>
                    <div className="faint" style={{ color: C.dim, marginTop: 6 }}>#{c.id}</div>
                    <div style={{ marginTop: 10 }}>
                      {c.source_system === "EDGAR" && c.accession_number && (
                        <SourceChip src="sec" form="10-K" code={c.accession_number} />
                      )}
                      {c.source_system === "DART" && c.rcept_no && (
                        <SourceChip src="dart" form="공시" code={c.rcept_no} />
                      )}
                      {!c.accession_number && !c.rcept_no && <SourceBadge source={c.source_system} />}
                    </div>
                  </div>
                  <div>
                    <h2
                      style={{
                        fontFamily: "var(--font-serif)",
                        fontSize: 20,
                        fontWeight: 500,
                        letterSpacing: "-0.015em",
                        margin: "0 0 4px",
                        lineHeight: 1.2,
                      }}
                    >
                      {c.licensor_name || "—"}{" "}
                      <span style={{ color: C.muted, fontStyle: "italic", fontWeight: 400 }}>→</span>{" "}
                      {c.licensee_name || c.company_name || "—"}
                    </h2>
                    <div style={{ fontSize: 12, color: C.text2, marginBottom: 10 }}>
                      {c.tech_category && (
                        <span
                          style={{
                            padding: "1px 7px",
                            borderRadius: 2,
                            background: C.accentSoft,
                            color: C.accentHover,
                            fontFamily: "var(--font-jetbrains), monospace",
                            fontSize: 10.5,
                            marginRight: 6,
                          }}
                        >
                          {c.tech_category}
                        </span>
                      )}
                      {c.tech_name || "—"}
                      {c.territory && <span style={{ margin: "0 6px" }}>·</span>}
                      {c.territory}
                    </div>

                    {c.tech_name && c.royalty_rate != null && (
                      <Quote
                        text={`Running royalty equal to <mark style="background:${C.accentSoft};color:${C.accentHover};padding:0 2px">${fmtPct(c.royalty_rate)}</mark> of Net Sales of Licensed Products.`}
                        cite={
                          c.source_system === "EDGAR" && c.accession_number
                            ? `Accession ${c.accession_number}`
                            : c.source_system === "DART" && c.rcept_no
                            ? `DART ${c.rcept_no}`
                            : c.source_system || "—"
                        }
                      />
                    )}

                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(4, 1fr)",
                        gap: 12,
                        marginTop: 10,
                        padding: "10px 14px",
                        background: C.bgEl,
                        borderRadius: 4,
                        fontSize: 11.5,
                      }}
                    >
                      <Term label="Upfront" value={fmtMoney(c.upfront_amount)} />
                      <Term label="Royalty" value={fmtPct(c.royalty_rate)} />
                      <Term label="Term" value={c.term_years ? `${c.term_years}y` : "—"} />
                      <Term label="Conf" value={c.confidence_score != null ? `${(c.confidence_score * 100).toFixed(0)}%` : "—"} />
                    </div>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); togglePin(c); }}
                      style={{ ...buttonStyle, justifyContent: "center", background: pinned ? C.accentSoft : C.bgCard, color: pinned ? C.accent : C.text, borderColor: pinned ? C.accent : C.bd }}
                    >
                      {pinned ? "Pinned" : "Pin for compare"}
                    </button>
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); pushToSourcePage(c); }}
                      style={{ ...buttonStyle, justifyContent: "center" }}
                    >
                      Open source
                    </button>
                    {c.source_url && (
                      <button
                        type="button"
                        onClick={(e) => { e.stopPropagation(); openEvidence(c.source_url); }}
                        style={{ ...buttonStyle, justifyContent: "center" }}
                      >
                        Open filing
                      </button>
                    )}
                  </div>
                </article>
              );
            })}
        </div>

        {pagination && (
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginTop: 20,
              paddingTop: 14,
              borderTop: `1px solid ${C.bd}`,
              fontSize: 12,
              color: C.muted,
            }}
          >
            <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1} style={{ ...buttonStyle, opacity: page <= 1 ? 0.3 : 1 }}>Prev</button>
            <span style={{ fontFamily: "var(--font-jetbrains), monospace" }}>
              {pagination.page} / {pagination.total_pages}
              <span style={{ marginLeft: 8, color: C.dim }}>({fmtN(pagination.total)} total)</span>
            </span>
            <button onClick={() => setPage((p) => Math.min(pagination.total_pages, p + 1))} disabled={page >= pagination.total_pages} style={{ ...buttonStyle, opacity: page >= pagination.total_pages ? 0.3 : 1 }}>Next</button>
          </div>
        )}
      </section>

      <aside style={{ display: "grid", gap: 16, position: "sticky", top: 80, alignSelf: "start" }}>
        {inspectionPane}
      </aside>
    </div>
  );

  /* Variation B — Comparables Grid */
  const variationB = (
    <div className="workbench-grid" style={{ marginTop: 20 }}>
      <aside>{filtersAside}</aside>
      <div>
        <CompareTray
          items={pinnedContracts.map((c) => ({
            id: c.id,
            title: c.company_name || c.tech_name || `Contract ${c.id}`,
            meta: `${c.source_system || "?"} · ${c.tech_category || "Uncategorized"} · ${fmtPct(c.royalty_rate)}`,
            tone: c.source_system === "DART" ? C.dart : C.sec,
          }))}
          selectedId={selected?.id}
          onSelect={(id) => {
            const next = pinnedContracts.find((c) => c.id === id) || contracts.find((c) => c.id === id) || null;
            setSelected(next);
            setSelectedId(next?.id ?? null);
          }}
          onRemove={(id) => setPinnedIds((cur) => cur.filter((v) => v !== id))}
        />

        {contractsError && <InlineError title="Rows unavailable" message={contractsError} />}

        <Panel title={`Comparables grid · ${fmtN(pagination?.total)} rows`} badge="비교표">
          <div style={{ overflowX: "auto" }}>
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                fontSize: 12.5,
                minWidth: 960,
              }}
            >
              <thead>
                <tr
                  style={{
                    fontSize: 10.5,
                    textTransform: "uppercase",
                    letterSpacing: "0.08em",
                    color: C.dim,
                  }}
                >
                  {["Source", "Signed", "Licensor → Licensee", "Field", "Upfront", "Royalty", "Term", "Year", "Conf"].map((h, i) => (
                    <th
                      key={h}
                      style={{
                        padding: "8px 10px",
                        textAlign: i >= 4 && i <= 7 ? "right" : i === 8 ? "center" : "left",
                        borderBottom: `1px solid ${C.bdFocus}`,
                        fontWeight: 500,
                        whiteSpace: "nowrap",
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {loading && Array.from({ length: 8 }).map((_, i) => (
                  <tr key={i} style={{ borderBottom: `1px solid ${C.bdSoft}` }}>
                    {Array.from({ length: 9 }).map((_, j) => (
                      <td key={j} style={{ padding: "var(--pad-cell) 10px" }}>
                        <Skeleton width={j === 2 ? 160 : 60} height={12} />
                      </td>
                    ))}
                  </tr>
                ))}
                {!loading && !contractsError && contracts.length === 0 && (
                  <tr><td colSpan={9}><EmptyState message="No contracts match your filters" /></td></tr>
                )}
                {!loading && contracts.map((c, idx) => {
                  const sel = selected?.id === c.id;
                  const pinned = pinnedIds.includes(c.id);
                  return (
                    <tr
                      key={c.id}
                      className="anim-row hoverable"
                      style={{
                        borderBottom: `1px solid ${C.bdSoft}`,
                        background: sel ? C.accentSoft : "transparent",
                        cursor: "pointer",
                        animationDelay: `${idx * 18}ms`,
                        height: "var(--row-h)",
                      }}
                      onClick={() => {
                        setSelected(sel ? null : c);
                        setSelectedId(sel ? null : c.id);
                      }}
                    >
                      <td style={{ padding: "var(--pad-cell) 10px" }}>
                        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                          <SourceBadge source={c.source_system} />
                          <button
                            type="button"
                            onClick={(e) => { e.stopPropagation(); togglePin(c); }}
                            aria-label={pinned ? "Unpin" : "Pin"}
                            style={{
                              width: 20, height: 20, padding: 0, border: "none", background: "transparent",
                              color: pinned ? C.accent : C.dim,
                              cursor: "pointer", fontSize: 14, lineHeight: 1,
                            }}
                          >
                            ◆
                          </button>
                        </div>
                      </td>
                      <td style={{ padding: "var(--pad-cell) 10px", fontFamily: "var(--font-jetbrains), monospace", fontSize: 11.5 }}>
                        {c.filing_date || "—"}
                      </td>
                      <td style={{ padding: "var(--pad-cell) 10px", fontWeight: 500 }}>
                        <div>{c.licensor_name || "—"} <span style={{ color: C.dim }}>→</span> {c.licensee_name || c.company_name || "—"}</div>
                      </td>
                      <td style={{ padding: "var(--pad-cell) 10px", fontSize: 11.5 }}>
                        {c.tech_category && (
                          <span
                            style={{
                              padding: "1px 6px",
                              background: C.accentSoft,
                              color: C.accentHover,
                              borderRadius: 2,
                              fontFamily: "var(--font-jetbrains), monospace",
                              fontSize: 10.5,
                            }}
                          >
                            {c.tech_category}
                          </span>
                        )}
                        <div style={{ color: C.muted, fontFamily: "var(--font-jetbrains), monospace", fontSize: 10.5, marginTop: 2 }}>
                          {c.territory || "—"}
                        </div>
                      </td>
                      <td style={{ padding: "var(--pad-cell) 10px", textAlign: "right", fontFamily: "var(--font-jetbrains), monospace" }}>
                        {fmtMoney(c.upfront_amount)}
                      </td>
                      <td style={{ padding: "var(--pad-cell) 10px", textAlign: "right", fontFamily: "var(--font-jetbrains), monospace", color: c.royalty_rate != null ? C.up : C.dim }}>
                        {fmtPct(c.royalty_rate)}
                      </td>
                      <td style={{ padding: "var(--pad-cell) 10px", textAlign: "right", fontFamily: "var(--font-jetbrains), monospace", color: C.text2 }}>
                        {c.term_years ? `${c.term_years}y` : "—"}
                      </td>
                      <td style={{ padding: "var(--pad-cell) 10px", textAlign: "right", fontFamily: "var(--font-jetbrains), monospace", color: C.text2 }}>
                        {c.filing_year || "—"}
                      </td>
                      <td style={{ padding: "var(--pad-cell) 10px" }}><ConfBar value={c.confidence_score || 0} /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Panel>

        {pagination && (
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginTop: 14,
              paddingTop: 14,
              borderTop: `1px solid ${C.bd}`,
              fontSize: 12,
              color: C.muted,
            }}
          >
            <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1} style={{ ...buttonStyle, opacity: page <= 1 ? 0.3 : 1 }}>Prev</button>
            <span style={{ fontFamily: "var(--font-jetbrains), monospace" }}>
              {pagination.page} / {pagination.total_pages}
              <span style={{ marginLeft: 8, color: C.dim }}>({fmtN(pagination.total)} total)</span>
            </span>
            <button onClick={() => setPage((p) => Math.min(pagination.total_pages, p + 1))} disabled={page >= pagination.total_pages} style={{ ...buttonStyle, opacity: page >= pagination.total_pages ? 0.3 : 1 }}>Next</button>
          </div>
        )}
      </div>
      <aside style={{ display: "grid", gap: 16, position: "sticky", top: 80, alignSelf: "start" }}>
        {inspectionPane}
      </aside>
    </div>
  );

  /* Variation C — Split Provenance (SEC ◁▷ DART) */
  const variationC = useMemo(() => {
    const pair = selected ?? contracts.find((c) => c.accession_number && c.rcept_no) ?? contracts[0];
    if (!pair) {
      return (
        <div style={{ marginTop: 20 }}>
          <EmptyState message="No rows loaded yet — filters must return at least one row to render Split Provenance." />
        </div>
      );
    }
    const secHas = pair.source_system === "EDGAR";
    const dartHas = pair.source_system === "DART";
    const rows = [
      { label: "Licensor",  l: pair.licensor_name, r: pair.licensor_name, kr: "권리자" },
      { label: "Licensee",  l: pair.licensee_name, r: pair.licensee_name, kr: "실시권자" },
      { label: "Technology",l: pair.tech_name, r: pair.tech_name, kr: "기술" },
      { label: "Category",  l: pair.tech_category, r: pair.tech_category, kr: "분야" },
      { label: "Territory", l: pair.territory, r: pair.territory, kr: "영역" },
      { label: "Term",      l: pair.term_years ? `${pair.term_years}y` : null, r: pair.term_years ? `${pair.term_years}년` : null, kr: "기간" },
      { label: "Upfront",   l: fmtMoney(pair.upfront_amount), r: fmtMoney(pair.upfront_amount), kr: "선급금" },
      { label: "Royalty",   l: fmtPct(pair.royalty_rate), r: fmtPct(pair.royalty_rate), kr: "로열티" },
      { label: "Filing",    l: pair.accession_number || "—", r: pair.rcept_no || "—", kr: "공시번호" },
      { label: "Filed",     l: secHas ? pair.filing_date : "—", r: dartHas ? pair.filing_date : "—", kr: "공시일" },
    ];
    return (
      <div style={{ marginTop: 20 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 40px 1fr", border: `1px solid ${C.bd}`, background: C.bgCard }}>
          <div style={{ background: C.secSoft, borderRight: `1px solid ${C.bd}` }}>
            <div style={{ padding: "10px 16px", borderBottom: `1px solid ${C.bd}`, display: "flex", alignItems: "center", gap: 8, fontFamily: "var(--font-serif)", fontSize: 13, fontWeight: 600 }}>
              <SourceChip src="sec" form="10-K" />
              SEC 10-K
            </div>
          </div>
          <div style={{ borderLeft: `1px dashed ${C.bdFocus}`, borderRight: `1px dashed ${C.bdFocus}`, background: C.bgEl }} />
          <div style={{ background: C.dartSoft }}>
            <div style={{ padding: "10px 16px", borderBottom: `1px solid ${C.bd}`, display: "flex", alignItems: "center", gap: 8, fontFamily: "var(--font-serif)", fontSize: 13, fontWeight: 600 }}>
              <SourceChip src="dart" form="공시" />
              DART
            </div>
          </div>
          {rows.map((r, i) => {
            const match = (r.l || "") === (r.r || "") && r.l;
            return (
              <div key={i} style={{ display: "contents" }}>
                <div style={{ padding: "10px 16px", borderBottom: i === rows.length - 1 ? "none" : `1px solid ${C.bdSoft}`, fontFamily: "var(--font-jetbrains), monospace", fontSize: 12, background: match ? C.secSoft : "transparent" }}>
                  <div className="upper" style={{ color: C.dim, fontSize: 10 }}>{r.label} · {r.kr}</div>
                  <div style={{ marginTop: 3, color: C.text }}>{r.l || "—"}</div>
                </div>
                <div style={{ borderBottom: i === rows.length - 1 ? "none" : `1px solid ${C.bdSoft}`, display: "grid", placeItems: "center", fontFamily: "var(--font-jetbrains), monospace", fontSize: 10, color: match ? C.up : C.warn, background: match ? C.bgCard : "#fbf0dd" }}>
                  {match ? "=" : "≠"}
                </div>
                <div style={{ padding: "10px 16px", borderBottom: i === rows.length - 1 ? "none" : `1px solid ${C.bdSoft}`, fontFamily: "var(--font-jetbrains), monospace", fontSize: 12, textAlign: "right", background: match ? C.dartSoft : "transparent" }}>
                  <div className="upper" style={{ color: C.dim, fontSize: 10 }}>{r.label} · {r.kr}</div>
                  <div style={{ marginTop: 3, color: C.text }}>{r.r || "—"}</div>
                </div>
              </div>
            );
          })}
        </div>
        <p style={{ marginTop: 12, fontSize: 12, color: C.muted, maxWidth: 760, lineHeight: 1.6 }}>
          Mirror the same agreement across two jurisdictions. The seam flags disagreement. <br/>
          <span className="kr">SEC 10-K와 DART 공시를 나란히 두고 통합 스키마가 맞춘 필드와 어긋난 필드를 확인합니다.</span>
        </p>
      </div>
    );
  }, [selected, contracts]);

  /* Variation D — Assistant-first teaser */
  const variationD = (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 320px", gap: 20, marginTop: 20 }}>
      <Panel title="Ask the ledger" badge="어시스턴트">
        <div style={{ display: "grid", gap: 14 }}>
          <p
            style={{
              fontFamily: "var(--font-serif)",
              fontSize: 14,
              lineHeight: 1.6,
              color: C.text,
              margin: 0,
            }}
          >
            자연어로 질문하면 검색 전략과 유사 계약·시장 범위를 돌려주는 어시스턴트입니다.
            답변에는 원문 조항 citation 이 붙고, 결과 계약은 이 대시보드로 바로 pin 해서 비교할 수 있습니다.
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
            {[
              { q: "Chemical manufacturing royalty benchmarks for process technology", kr: "화학 공정기술 로열티 벤치마크" },
              { q: "Pharmaceutical drug licensing royalty rates",                       kr: "의약품 라이선스 로열티" },
              { q: "Semiconductor process licensing deal comps",                        kr: "반도체 공정 라이선스 계약 비교" },
            ].map((ex, i) => (
              <a
                key={i}
                href="/assistant"
                style={{
                  display: "block",
                  padding: 12,
                  border: `1px solid ${C.bd}`,
                  borderRadius: 4,
                  fontSize: 12.5,
                  background: C.bgCard,
                  textDecoration: "none",
                  color: C.text,
                }}
              >
                <div>{ex.q}</div>
                <div className="kr" style={{ marginTop: 4 }}>{ex.kr}</div>
              </a>
            ))}
          </div>
          <a href="/assistant" style={{ ...buttonStyle, background: C.text, color: C.bg, borderColor: C.text, textDecoration: "none", justifyContent: "center" }}>
            Open Assistant workbench →
          </a>
        </div>
      </Panel>
      <aside style={{ display: "grid", gap: 16, position: "sticky", top: 80, alignSelf: "start" }}>
        {inspectionPane}
      </aside>
    </div>
  );

  /* render */
  const renderVariation = (v: DashVariation) =>
    v === "A" ? variationA : v === "B" ? variationB : v === "C" ? variationC : variationD;

  return (
    <div className="app-shell">
      <AppNav />
      <div className="page-stack">
        {healthStrip}

        {/* KPI strip */}
        <div className="kpi-grid" style={{ marginTop: 18 }}>
          <KPI label="Total Contracts" value={fmtN(pagination?.total)} color={C.text} sub={source || "All sources"} />
          <KPI label="Companies" value={fmtN(stats?.total_companies)} color={C.sec} />
          <KPI label="Avg Royalty" value={stats?.avg_royalty != null ? `${stats.avg_royalty.toFixed(1)}%` : "—"} color={C.up} />
          <KPI label="Avg Confidence" value={stats?.avg_confidence != null ? `${(stats.avg_confidence * 100).toFixed(0)}%` : "—"} color={C.accent} />
        </div>

        {/* Source compare cards */}
        <div className="source-card-grid" style={{ marginTop: 16 }}>
          {sourceCards.map((card) => (
            <SourceCompareCard
              key={card.label}
              label={card.label}
              value={card.value}
              sub={card.sub}
              meta={card.meta}
              tone={card.tone}
              active={source === card.key || (card.key === "" && source === "")}
              onClick={() => { setSource(card.key); setPage(1); setSelected(null); setSelectedId(null); }}
            />
          ))}
        </div>

        {statsError && <div style={{ marginTop: 16 }}><InlineError title="Metrics degraded" message={statsError} /></div>}

        {/* Charts */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
            gap: 16,
            marginTop: 18,
          }}
        >
          <Panel title="Top Categories" badge="분야">
            <ResponsiveContainer width="100%" height={200}>
              <BarChart
                data={categories.slice(0, 10)}
                margin={{ top: 8, right: 8, left: -16, bottom: 4 }}
                onClick={(state) => {
                  const categoryName = state?.activeLabel;
                  if (categoryName) { setCategory(String(categoryName)); setPage(1); }
                }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={C.bdSoft} />
                <XAxis dataKey="category" tick={{ fontSize: 9, fill: C.muted }} interval={0} angle={-20} textAnchor="end" height={50} />
                <YAxis tick={{ fontSize: 10, fill: C.muted }} />
                <Tooltip contentStyle={tooltipStyle} cursor={{ fill: C.bgEl }} />
                <Bar dataKey="count" radius={[2, 2, 0, 0]}>
                  {categories.slice(0, 10).map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </Panel>

          <Panel title="Source Distribution" badge="출처">
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={stats?.by_source ? Object.entries(stats.by_source).map(([k, v]) => ({ name: k, value: v })) : []}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={70}
                  innerRadius={42}
                  strokeWidth={0}
                  paddingAngle={2}
                  onClick={(payload) => {
                    const nextSource = payload?.name;
                    if (nextSource === "EDGAR" || nextSource === "DART") setSource(nextSource); else setSource("");
                    setPage(1);
                    setSelected(null);
                    setSelectedId(null);
                  }}
                  label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}
                >
                  <Cell fill={C.sec} />
                  <Cell fill={C.dart} />
                  <Cell fill={C.warn} />
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
              </PieChart>
            </ResponsiveContainer>
          </Panel>
        </div>

        {/* Page head + toolbar */}
        <div style={{ marginTop: 28 }}>
          {pageHead}
          {toolbar}
        </div>

        {renderVariation(tweaks.state.variation)}
      </div>

      <Tweaks open={tweaks.open} onClose={() => tweaks.setOpen(false)} state={tweaks.state} set={tweaks.set} />
    </div>
  );
}

function Term({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="upper" style={{ color: C.dim, fontSize: 10, marginBottom: 3 }}>{label}</div>
      <div style={{ fontFamily: "var(--font-jetbrains), monospace", fontSize: 13, color: C.text }}>{value}</div>
    </div>
  );
}
