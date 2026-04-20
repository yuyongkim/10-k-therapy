"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, Area, AreaChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { AppNav } from "@/components/app-nav";
import {
  C, CHART_COLORS, fmtN, fmtPct, fmtMoney,
  tooltipStyle, inputStyle, selectStyle, buttonStyle,
} from "@/components/theme";
import {
  KPI, ConfBar, FilterField, DetailBox, DRow,
  CompareTray, Panel, SourceBadge, SourceChip, HealthStrip,
  EmptyState, TabBtn, Tweaks, useTweaks, StatPill,
} from "@/components/ui";

const API = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api"}/dart`;
const SOURCE_HANDOFF_KEY = "sec-dashboard-source-handoff-v1";
const DART_WORKBENCH_KEY = "dart-source-workbench-state-v1";
const DART_SEARCH_WORKBENCH_KEY = "dart-search-workbench-state-v1";

/* ── types ── */
type ContractStats = {
  total_contracts: number; total_companies: number; avg_confidence: number | null;
  avg_royalty: number | null; contracts_with_royalty: number;
  by_category: { category: string; count: number }[];
  extraction_status: string;
};
type SectionStats = {
  total_filings: number; total_companies: number; total_sections: number;
  high_signal_sections: number; med_signal_sections: number;
  signal_distribution: { high: number; medium: number; low: number; none: number };
  by_month: { month: string; count: number }[];
};
type Contract = {
  id: number; company: string | null; licensor: string | null; licensee: string | null;
  tech_name: string | null; category: string | null; royalty_rate: number | null;
  upfront_amount: number | null; upfront_currency: string | null; territory: string | null;
  term_years: number | null; exclusivity: string | null; confidence: number | null;
  model: string | null; year: number | null; reasoning: string | null;
  accession_number: string | null; rcept_no: string | null; filing_date: string | null; source_url: string | null;
};
type Pagination = { page: number; page_size: number; total: number; total_pages: number };
type SimilarCase = {
  id: string; source: string; company: string; category: string;
  score: number; distance: number; snippet: string;
};
type SimilarResult = {
  rag_results: SimilarCase[];
  db_contracts: { licensor: string | null; tech_name: string | null; category: string | null; royalty_rate: number | null; upfront_amount: number | null; source: string | null; confidence: number | null }[];
  benchmark: { royalty?: { min: number; max: number; median: number; mean: number; count: number }; upfront?: { min: number; max: number; median: number; count: number } } | null;
};

export default function DartDashboard() {
  const initialHandoff = (() => {
    if (typeof window === "undefined") return { search: "", category: "", minConf: "" };
    try {
      const handoff = window.localStorage.getItem(SOURCE_HANDOFF_KEY);
      if (!handoff) return { search: "", category: "", minConf: "" };
      const parsed = JSON.parse(handoff) as {
        route?: string; search?: string; category?: string; minConf?: string;
      };
      if (parsed.route !== "/dart") return { search: "", category: "", minConf: "" };
      window.localStorage.removeItem(SOURCE_HANDOFF_KEY);
      return { search: parsed.search || "", category: parsed.category || "", minConf: parsed.minConf || "" };
    } catch {
      return { search: "", category: "", minConf: "" };
    }
  })();
  const initialWorkbench = (() => {
    if (typeof window === "undefined") return { pinnedIds: [] as number[], selectedId: null as number | null };
    try {
      const saved = window.localStorage.getItem(DART_WORKBENCH_KEY);
      if (!saved) return { pinnedIds: [], selectedId: null };
      const parsed = JSON.parse(saved) as { pinnedIds?: number[]; selectedId?: number | null };
      return {
        pinnedIds: Array.isArray(parsed.pinnedIds) ? parsed.pinnedIds.filter((id) => typeof id === "number").slice(0, 3) : [],
        selectedId: typeof parsed.selectedId === "number" ? parsed.selectedId : null,
      };
    } catch {
      return { pinnedIds: [] as number[], selectedId: null as number | null };
    }
  })();
  const initialSearchWorkbench = (() => {
    if (typeof window === "undefined") return { searchQuery: "", searchResult: null as SimilarResult | null };
    try {
      const saved = window.localStorage.getItem(DART_SEARCH_WORKBENCH_KEY);
      if (!saved) return { searchQuery: "", searchResult: null };
      const parsed = JSON.parse(saved) as { searchQuery?: string; searchResult?: SimilarResult | null };
      return {
        searchQuery: parsed.searchQuery || "",
        searchResult: parsed.searchResult || null,
      };
    } catch {
      return { searchQuery: "", searchResult: null as SimilarResult | null };
    }
  })();

  const [cStats, setCStats] = useState<ContractStats | null>(null);
  const [sStats, setSStats] = useState<SectionStats | null>(null);
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState(initialHandoff.search);
  const [category, setCategory] = useState(initialHandoff.category);
  const [minConf, setMinConf] = useState(initialHandoff.minConf);
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<number | null>(initialWorkbench.selectedId);
  const [pinnedIds, setPinnedIds] = useState<number[]>(initialWorkbench.pinnedIds);
  const [tab, setTab] = useState<"contracts" | "search">("contracts");
  const [searchQuery, setSearchQuery] = useState(initialSearchWorkbench.searchQuery);
  const [searchResult, setSearchResult] = useState<SimilarResult | null>(initialSearchWorkbench.searchResult);
  const [searching, setSearching] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  const tweaks = useTweaks();

  useEffect(() => {
    fetch(`${API}/contracts/stats`).then(r => r.json()).then(setCStats).catch(() => {});
    fetch(`${API}/stats`).then(r => r.json()).then(setSStats).catch(() => {});
  }, []);

  useEffect(() => {
    const p = new URLSearchParams({ page: String(page), page_size: "25", sort: "confidence_score:desc" });
    if (search) p.set("search", search);
    if (category) p.set("category", category);
    if (minConf) p.set("min_confidence", minConf);
    fetch(`${API}/contracts?${p}`)
      .then(r => r.json())
      .then(d => { setContracts(d.data || []); setPagination(d.pagination); setLoading(false); })
      .catch(() => setLoading(false));
  }, [page, search, category, minConf]);

  useEffect(() => {
    try {
      window.localStorage.setItem(DART_WORKBENCH_KEY, JSON.stringify({ pinnedIds, selectedId }));
    } catch {}
  }, [pinnedIds, selectedId]);

  useEffect(() => {
    try {
      window.localStorage.setItem(DART_SEARCH_WORKBENCH_KEY, JSON.stringify({ searchQuery, searchResult }));
    } catch {}
  }, [searchQuery, searchResult]);

  const selected = selectedId != null
    ? contracts.find((c) => c.id === selectedId) || null
    : null;

  const pinnedContracts = pinnedIds
    .map((id) => contracts.find((c) => c.id === id) || (selected?.id === id ? selected : null))
    .filter((c): c is Contract => Boolean(c));

  const togglePin = (c: Contract) => {
    setPinnedIds((cur) => cur.includes(c.id) ? cur.filter((id) => id !== c.id) : [...cur, c.id].slice(-3));
  };

  const doSimilarSearch = useCallback(async () => {
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      const res = await fetch(`${API}/similar-cases`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: searchQuery, max_results: 10 }),
      });
      setSearchResult(await res.json());
    } catch { setSearchResult(null); }
    setSearching(false);
  }, [searchQuery]);

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

  const categories = cStats?.by_category || [];
  const signalPie = sStats ? [
    { name: "High 6+",  value: sStats.signal_distribution.high,   color: C.up },
    { name: "Med 3–5",  value: sStats.signal_distribution.medium, color: C.sec },
    { name: "Low 1–2",  value: sStats.signal_distribution.low,    color: C.warn },
    { name: "None",     value: sStats.signal_distribution.none,   color: C.bd },
  ] : [];

  return (
    <div className="app-shell">
      <AppNav />
      <div className="page-stack">
        <HealthStrip
          items={[
            { label: "DART slice", labelKr: "DART 슬라이스", value: fmtN(pagination?.total), tone: "muted" },
            { label: "Filings", labelKr: "공시 수", value: fmtN(sStats?.total_filings), tone: "muted" },
            { label: "Companies", labelKr: "기업 수", value: fmtN(cStats?.total_companies), tone: "muted" },
            { label: "Avg royalty", labelKr: "평균 로열티", value: cStats?.avg_royalty != null ? `${cStats.avg_royalty}%` : "—", tone: "up" },
            {
              label: "Extraction",
              labelKr: "추출 상태",
              value: cStats?.extraction_status === "running" ? "Running" : cStats?.extraction_status || "—",
              tone: cStats?.extraction_status === "running" ? "cyan" : "muted",
            },
          ]}
        />

        {/* Page head */}
        <header style={{ marginTop: 22, marginBottom: 16 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 8 }}>
            <span className="upper" style={{ fontFamily: "var(--font-jetbrains), monospace", color: C.dim }}>
              SOURCE · DART 공시 + RAG
            </span>
            <span style={{ flex: 1, borderTop: `1px solid ${C.bd}` }} />
            <span className="upper" style={{ fontFamily: "var(--font-jetbrains), monospace", color: C.dim }}>
              {fmtN(sStats?.total_sections)} SECTIONS
            </span>
          </div>
          <h1 style={{
            fontFamily: "var(--font-serif)",
            fontSize: 30,
            fontWeight: 500,
            letterSpacing: "-0.02em",
            margin: "0 0 8px",
            lineHeight: 1.1,
          }}>
            DART <em style={{ fontStyle: "italic", color: C.accent }}>공시</em> · IP intelligence
          </h1>
          <p style={{ fontSize: 13, color: C.text2, maxWidth: 720, lineHeight: 1.65 }}>
            Korean DART filings with extracted license contracts plus a RAG search over disclosure snippets.
            <span style={{ display: "block", marginTop: 2, color: C.muted, fontSize: 12 }}>
              DART 공시에서 추출한 라이선스 계약과, 공시 구절 전체에 대한 RAG 의미검색을 함께 제공합니다.
            </span>
          </p>
        </header>

        {/* KPIs */}
        <div className="kpi-grid">
          <KPI label="Contracts" value={fmtN(cStats?.total_contracts)} color={C.dart} sub="DART filings" />
          <KPI label="Avg Royalty" value={cStats?.avg_royalty != null ? `${cStats.avg_royalty}%` : "—"} color={C.up} />
          <KPI label="With Royalty" value={fmtN(cStats?.contracts_with_royalty)} color={C.warn} />
          <KPI label="High Signal" value={fmtN(sStats?.high_signal_sections)} color={C.text} sub="signal ≥ 6" />
        </div>

        {/* Charts */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 16, marginTop: 16 }}>
          <Panel title="Technology categories" badge={`${categories.length} types`}>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={categories.slice(0, 8)} margin={{ top: 8, right: 8, left: -16, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={C.bdSoft} />
                <XAxis dataKey="category" tick={{ fontSize: 10, fill: C.muted }} interval={0} angle={-20} textAnchor="end" height={50} />
                <YAxis tick={{ fontSize: 10, fill: C.muted }} />
                <Tooltip contentStyle={tooltipStyle} cursor={{ fill: C.bgEl }} />
                <Bar dataKey="count" radius={[2, 2, 0, 0]}>
                  {categories.slice(0, 8).map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </Panel>

          <Panel title="Signal distribution" badge={fmtN(sStats?.total_sections)}>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={signalPie}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={70}
                  innerRadius={42}
                  strokeWidth={0}
                  label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}
                >
                  {signalPie.map((s, i) => <Cell key={i} fill={s.color} />)}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
              </PieChart>
            </ResponsiveContainer>
          </Panel>

          <Panel title="Filing trend" badge="monthly">
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={sStats?.by_month || []} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                <defs>
                  <linearGradient id="dartAG" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={C.dart} stopOpacity={0.4} />
                    <stop offset="95%" stopColor={C.dart} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={C.bdSoft} />
                <XAxis dataKey="month" tick={{ fontSize: 9, fill: C.muted }} />
                <YAxis tick={{ fontSize: 10, fill: C.muted }} />
                <Tooltip contentStyle={tooltipStyle} />
                <Area type="monotone" dataKey="count" stroke={C.dart} fill="url(#dartAG)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </Panel>
        </div>

        {/* Tabs */}
        <div style={{ display: "flex", gap: 0, marginTop: 22, borderBottom: `1px solid ${C.bd}` }}>
          <TabBtn active={tab === "contracts"} onClick={() => setTab("contracts")}>
            License Agreements · <span className="kr">계약</span> ({fmtN(pagination?.total)})
          </TabBtn>
          <TabBtn active={tab === "search"} onClick={() => setTab("search")}>
            Similar Case Search (RAG) · <span className="kr">유사 공시 검색</span>
          </TabBtn>
          <span style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 8 }}>
            <button type="button" onClick={() => tweaks.setOpen(true)} style={buttonStyle}>Tweaks</button>
            {copied && <StatPill label="Clipboard" value={copied} color={copied.includes("failed") ? C.accent : C.up} />}
          </span>
        </div>

        {/* Contracts tab */}
        {tab === "contracts" && (
          <div className="workbench-grid" style={{ marginTop: 16 }}>
            <aside>
              <Panel title="Filters" badge="필터">
                <FilterField label="Search">
                  <input value={search} onChange={(e) => { setPage(1); setSearch(e.target.value); }} style={inputStyle} placeholder="company, tech…" />
                </FilterField>
                <FilterField label="Category">
                  <select value={category} onChange={(e) => { setPage(1); setCategory(e.target.value); }} style={selectStyle}>
                    <option value="">All</option>
                    {categories.map(c => <option key={c.category} value={c.category}>{c.category} ({c.count})</option>)}
                  </select>
                </FilterField>
                <FilterField label="Min Confidence">
                  <select value={minConf} onChange={(e) => { setPage(1); setMinConf(e.target.value); }} style={selectStyle}>
                    <option value="">Any</option>
                    <option value="0.6">60%+</option>
                    <option value="0.8">80%+</option>
                    <option value="0.9">90%+</option>
                  </select>
                </FilterField>
                <button
                  onClick={() => { setSearch(""); setCategory(""); setMinConf(""); setPage(1); }}
                  style={{ ...buttonStyle, width: "100%", marginTop: 18, justifyContent: "center" }}
                >
                  Reset
                </button>
              </Panel>
            </aside>

            <div>
              <CompareTray
                items={pinnedContracts.map((c) => ({
                  id: c.id,
                  title: c.company || c.tech_name || `Contract ${c.id}`,
                  meta: `DART · ${c.category || "—"} · ${c.year || "—"} · ${fmtPct(c.royalty_rate)}`,
                  tone: C.dart,
                }))}
                selectedId={selectedId}
                onSelect={(id) => {
                  const next = pinnedContracts.find((c) => c.id === id) || contracts.find((c) => c.id === id) || null;
                  setSelectedId(next?.id ?? null);
                }}
                onRemove={(id) => setPinnedIds((cur) => cur.filter((v) => v !== id))}
              />

              <Panel title="DART agreements" badge="비교표">
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5, minWidth: 900 }}>
                    <thead>
                      <tr style={{ fontSize: 10.5, textTransform: "uppercase", letterSpacing: "0.08em", color: C.dim }}>
                        {["공시 기업 · Parties", "Technology", "Category", "Royalty", "Upfront", "Term", "Conf"].map((h, i) => (
                          <th
                            key={h}
                            style={{
                              padding: "8px 10px",
                              textAlign: i >= 3 && i <= 5 ? "right" : i === 6 ? "center" : "left",
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
                      {loading && <tr><td colSpan={7} style={{ padding: "48px 0", textAlign: "center", color: C.dim }}>Loading…</td></tr>}
                      {!loading && contracts.length === 0 && <tr><td colSpan={7}><EmptyState message="No data for current filters" /></td></tr>}
                      {!loading && contracts.map((c, idx) => {
                        const sel = selected?.id === c.id;
                        const pinned = pinnedIds.includes(c.id);
                        return (
                          <tr
                            key={c.id}
                            className="anim-row hoverable"
                            onClick={() => setSelectedId(sel ? null : c.id)}
                            style={{
                              borderBottom: `1px solid ${C.bdSoft}`,
                              background: sel ? C.accentSoft : "transparent",
                              cursor: "pointer",
                              animationDelay: `${idx * 18}ms`,
                            }}
                          >
                            <td style={{ padding: "10px" }}>
                              <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                                <div style={{ flex: 1, minWidth: 0 }}>
                                  <div
                                    style={{
                                      fontFamily: "var(--font-serif)",
                                      fontSize: 14,
                                      fontWeight: 600,
                                      color: C.text,
                                      letterSpacing: "-0.01em",
                                      lineHeight: 1.2,
                                    }}
                                  >
                                    {c.company || "—"}
                                  </div>
                                  <div
                                    style={{
                                      marginTop: 3,
                                      fontSize: 11,
                                      color: C.muted,
                                      lineHeight: 1.4,
                                      overflow: "hidden",
                                      textOverflow: "ellipsis",
                                      whiteSpace: "nowrap",
                                    }}
                                    title={`${c.licensor || "—"} → ${c.licensee || "—"}`}
                                  >
                                    {c.licensor || "—"}{" "}
                                    <span style={{ color: C.dim }}>→</span>{" "}
                                    {c.licensee || c.company || "—"}
                                  </div>
                                </div>
                                <button
                                  type="button"
                                  onClick={(e) => { e.stopPropagation(); togglePin(c); }}
                                  aria-label={pinned ? "Unpin" : "Pin"}
                                  style={{
                                    width: 20, height: 20, padding: 0, border: "none", background: "transparent",
                                    color: pinned ? C.accent : C.dim, cursor: "pointer", fontSize: 14, lineHeight: 1,
                                    flexShrink: 0,
                                  }}
                                >
                                  ◆
                                </button>
                              </div>
                            </td>
                            <td
                              title={c.tech_name || undefined}
                              style={{
                                padding: "var(--pad-cell) 10px",
                                color: C.text2,
                                maxWidth: 200,
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace: "nowrap",
                              }}
                            >
                              {c.tech_name || "—"}
                            </td>
                            <td style={{ padding: "var(--pad-cell) 10px" }}>
                              {c.category ? (
                                <span style={{
                                  background: C.dartSoft,
                                  color: C.dart,
                                  padding: "1px 7px",
                                  borderRadius: 2,
                                  fontSize: 10.5,
                                  fontFamily: "var(--font-jetbrains), monospace",
                                }}>{c.category}</span>
                              ) : "—"}
                            </td>
                            <td style={{ padding: "var(--pad-cell) 10px", textAlign: "right", fontFamily: "var(--font-jetbrains), monospace", color: c.royalty_rate != null ? C.up : C.dim }}>
                              {c.royalty_rate != null ? fmtPct(c.royalty_rate) : "—"}
                            </td>
                            <td style={{ padding: "var(--pad-cell) 10px", textAlign: "right", fontFamily: "var(--font-jetbrains), monospace", color: C.text2 }}>
                              {fmtMoney(c.upfront_amount, c.upfront_currency)}
                            </td>
                            <td style={{ padding: "var(--pad-cell) 10px", textAlign: "right", fontFamily: "var(--font-jetbrains), monospace", color: C.text2 }}>
                              {c.term_years != null ? `${c.term_years}y` : "—"}
                            </td>
                            <td style={{ padding: "var(--pad-cell) 10px" }}><ConfBar value={c.confidence || 0} /></td>
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
                    {pagination.page} / {pagination.total_pages} <span style={{ color: C.dim, marginLeft: 8 }}>({fmtN(pagination.total)})</span>
                  </span>
                  <button onClick={() => setPage((p) => Math.min(pagination.total_pages, p + 1))} disabled={page >= pagination.total_pages} style={{ ...buttonStyle, opacity: page >= pagination.total_pages ? 0.3 : 1 }}>Next</button>
                </div>
              )}
            </div>

            <aside style={{ position: "sticky", top: 80, alignSelf: "start" }}>
              <Panel title="Inspection pane" badge="상세">
                {selected ? (
                  <div style={{ display: "grid", gap: 14 }}>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                        <SourceBadge source="DART" />
                        {selected.rcept_no && <SourceChip src="dart" form="공시" code={selected.rcept_no} />}
                      </div>
                      <h3 style={{
                        marginTop: 8, marginBottom: 2,
                        fontFamily: "var(--font-serif)", fontSize: 18, fontWeight: 500, letterSpacing: "-0.01em",
                      }}>
                        {selected.company || "Unknown"}
                      </h3>
                      <div style={{ fontSize: 12, color: C.text2 }}>
                        {selected.model || "—"} · {selected.year || "—"}
                      </div>
                    </div>

                    <DetailBox title="Parties">
                      <DRow label="Licensor" value={selected.licensor} />
                      <DRow label="Licensee" value={selected.licensee} />
                    </DetailBox>
                    <DetailBox title="Technology">
                      <DRow label="Name" value={selected.tech_name} />
                      <DRow label="Category" value={selected.category} />
                    </DetailBox>
                    <DetailBox title="Financial">
                      <DRow label="Royalty" value={selected.royalty_rate != null ? fmtPct(selected.royalty_rate) : null} highlight />
                      <DRow label="Upfront" value={selected.upfront_amount != null ? fmtMoney(selected.upfront_amount, selected.upfront_currency) : null} />
                    </DetailBox>
                    <DetailBox title="Contract">
                      <DRow label="Term" value={selected.term_years != null ? `${selected.term_years}y` : null} />
                      <DRow label="Territory" value={selected.territory} />
                      <DRow label="Exclusivity" value={selected.exclusivity} />
                      <DRow label="Filing ref" value={selected.accession_number || selected.rcept_no} />
                      <DRow label="Filing date" value={selected.filing_date} />
                    </DetailBox>

                    {selected.reasoning && (
                      <DetailBox title="Source snippet">
                        <p style={{ fontFamily: "var(--font-serif)", fontSize: 13, color: C.text, lineHeight: 1.55, margin: 0, fontStyle: "italic" }}>
                          {selected.reasoning}
                        </p>
                      </DetailBox>
                    )}

                    <div style={{ display: "grid", gap: 6 }}>
                      {selected.source_url && (
                        <button
                          type="button"
                          onClick={() => openEvidence(selected.source_url)}
                          style={{ ...buttonStyle, width: "100%", justifyContent: "center", background: C.text, color: C.bg, borderColor: C.text }}
                        >
                          Open filing evidence
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => copyText("Contract context", JSON.stringify({
                          id: selected.id, source: "DART",
                          company: selected.company, licensor: selected.licensor, licensee: selected.licensee,
                          technology: selected.tech_name, category: selected.category,
                          royalty_rate: selected.royalty_rate,
                          upfront_amount: selected.upfront_amount, upfront_currency: selected.upfront_currency,
                          term_years: selected.term_years, territory: selected.territory, exclusivity: selected.exclusivity,
                          confidence: selected.confidence, year: selected.year, model: selected.model,
                          accession_number: selected.accession_number, rcept_no: selected.rcept_no,
                          filing_date: selected.filing_date, source_url: selected.source_url,
                        }, null, 2))}
                        style={{ ...buttonStyle, width: "100%", justifyContent: "center" }}
                      >
                        Copy contract context
                      </button>
                      <button type="button" onClick={() => setSelectedId(null)} style={{ ...buttonStyle, width: "100%", justifyContent: "center" }}>
                        Clear selection
                      </button>
                    </div>
                  </div>
                ) : (
                  <EmptyState message="Pick a row to inspect. Pin rows to keep them in the compare tray." />
                )}
              </Panel>
            </aside>
          </div>
        )}

        {/* Search tab */}
        {tab === "search" && (
          <div style={{ marginTop: 16 }}>
            <Panel title="RAG · Similar case search" badge="유사 공시 검색">
              <div style={{ display: "flex", gap: 8 }}>
                <input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && doSimilarSearch()}
                  style={{ ...inputStyle, flex: 1, marginTop: 0, padding: "10px 12px", fontSize: 14 }}
                  placeholder="예: 폴리에틸렌 촉매 로열티 · polyethylene catalyst royalty rate…"
                />
                <button
                  onClick={doSimilarSearch}
                  disabled={searching || !searchQuery.trim()}
                  style={{ ...buttonStyle, background: C.text, color: C.bg, borderColor: C.text, padding: "0 20px", height: 38, opacity: searching || !searchQuery.trim() ? 0.6 : 1 }}
                >
                  {searching ? "Searching…" : "Search"}
                </button>
              </div>

              <div style={{ marginTop: 10, display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                <button
                  type="button"
                  onClick={() => copyText("Search seed", searchQuery)}
                  disabled={!searchQuery.trim()}
                  style={{ ...buttonStyle, fontSize: 11, height: 24, padding: "0 10px", opacity: searchQuery.trim() ? 1 : 0.5 }}
                >
                  Copy search seed
                </button>
                {["폴리에틸렌 촉매 기술", "의약품 특허 로열티", "반도체 IP 라이선스", "배터리 기술이전", "pharmaceutical patent royalty"].map(q => (
                  <button
                    key={q}
                    onClick={() => setSearchQuery(q)}
                    style={{
                      padding: "4px 10px",
                      background: C.bgEl,
                      border: `1px solid ${C.bd}`,
                      borderRadius: 999,
                      color: C.text2,
                      fontSize: 11,
                      cursor: "pointer",
                      fontFamily: "inherit",
                    }}
                  >
                    {q}
                  </button>
                ))}
              </div>
            </Panel>

            {searchResult && (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 16 }}>
                {searchResult.benchmark && (searchResult.benchmark.royalty || searchResult.benchmark.upfront) && (
                  <div style={{ gridColumn: "1 / -1" }}>
                    <Panel title="Market benchmark" badge="시장 벤치마크">
                      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
                        <button
                          type="button"
                          onClick={() => copyText("Benchmark context", JSON.stringify(searchResult.benchmark, null, 2))}
                          style={{ ...buttonStyle, fontSize: 11, height: 24, padding: "0 10px" }}
                        >
                          Copy benchmark context
                        </button>
                      </div>
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                        {searchResult.benchmark.royalty && (
                          <BenchmarkBlock
                            label="Royalty rate"
                            median={`${searchResult.benchmark.royalty.median.toFixed(1)}%`}
                            min={`${searchResult.benchmark.royalty.min.toFixed(1)}%`}
                            max={`${searchResult.benchmark.royalty.max.toFixed(1)}%`}
                            extra={`mean ${searchResult.benchmark.royalty.mean.toFixed(1)}% · n=${searchResult.benchmark.royalty.count}`}
                            color={C.up}
                          />
                        )}
                        {searchResult.benchmark.upfront && (
                          <BenchmarkBlock
                            label="Upfront payment"
                            median={fmtMoney(searchResult.benchmark.upfront.median)}
                            min={fmtMoney(searchResult.benchmark.upfront.min)}
                            max={fmtMoney(searchResult.benchmark.upfront.max)}
                            extra={`n=${searchResult.benchmark.upfront.count}`}
                            color={C.warn}
                          />
                        )}
                      </div>
                    </Panel>
                  </div>
                )}

                <Panel title={`Matching DB contracts · ${searchResult.db_contracts.length}`} badge="DB 계약">
                  <div style={{ maxHeight: 320, overflowY: "auto" }}>
                    {searchResult.db_contracts.length === 0 && <EmptyState message="No DB matches" />}
                    {searchResult.db_contracts.map((c, i) => (
                      <div
                        key={i}
                        style={{
                          padding: "10px 0",
                          borderBottom: i < searchResult.db_contracts.length - 1 ? `1px solid ${C.bdSoft}` : "none",
                          display: "grid",
                          gridTemplateColumns: "1fr 1fr auto",
                          gap: 10,
                          fontSize: 12,
                          alignItems: "center",
                        }}
                      >
                        <div>
                          <div style={{ color: C.text, fontWeight: 500 }}>{c.licensor || "Unknown"}</div>
                          <div style={{ color: C.muted, fontSize: 11 }}>{c.tech_name || "—"}</div>
                        </div>
                        <div style={{ color: C.text2, fontSize: 11, display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                          {c.category && (
                            <span style={{ background: C.dartSoft, color: C.dart, padding: "1px 6px", borderRadius: 2, fontSize: 10.5, fontFamily: "var(--font-jetbrains), monospace" }}>
                              {c.category}
                            </span>
                          )}
                          <SourceBadge source={c.source} />
                        </div>
                        <div style={{ textAlign: "right", fontFamily: "var(--font-jetbrains), monospace" }}>
                          {c.royalty_rate != null && <span style={{ color: C.up, fontWeight: 600 }}>{c.royalty_rate.toFixed(1)}%</span>}
                          {c.upfront_amount != null && <span style={{ color: C.sec, marginLeft: 8 }}>{fmtMoney(c.upfront_amount)}</span>}
                          <div style={{ marginTop: 6 }}>
                            <button
                              type="button"
                              onClick={() => copyText("DB contract context", JSON.stringify(c, null, 2))}
                              style={{ ...buttonStyle, fontSize: 10, height: 22, padding: "0 8px" }}
                            >
                              Copy
                            </button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </Panel>

                <div style={{ gridColumn: "1 / -1" }}>
                  <Panel title={`Similar disclosures (RAG) · ${searchResult.rag_results.length}`} badge="유사 공시">
                    <div style={{ maxHeight: 420, overflowY: "auto" }}>
                      {searchResult.rag_results.length === 0 && <EmptyState message="No RAG results" />}
                      {searchResult.rag_results.map((r, i) => (
                        <div
                          key={i}
                          style={{
                            padding: "12px 0",
                            borderBottom: i < searchResult.rag_results.length - 1 ? `1px solid ${C.bdSoft}` : "none",
                          }}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
                            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                              <SourceBadge source={r.source?.toUpperCase() || null} />
                              <span style={{ fontFamily: "var(--font-serif)", fontSize: 14, fontWeight: 500, color: C.text, letterSpacing: "-0.01em" }}>
                                {r.company || "Unknown"}
                              </span>
                              {r.category && <span style={{ fontSize: 11, color: C.muted }}>· {r.category}</span>}
                            </div>
                            <span style={{ fontSize: 11, fontFamily: "var(--font-jetbrains), monospace", color: C.dim }}>
                              dist: {r.distance.toFixed(3)}
                            </span>
                          </div>
                          <p
                            style={{
                              marginTop: 6,
                              fontFamily: "var(--font-serif)",
                              fontSize: 13,
                              color: C.text2,
                              lineHeight: 1.6,
                              fontStyle: "italic",
                            }}
                          >
                            “{r.snippet}”
                          </p>
                          <div style={{ marginTop: 6 }}>
                            <button
                              type="button"
                              onClick={() => copyText("RAG snippet", `${r.company || "Unknown"} | ${r.category || "—"} | ${r.snippet}`)}
                              style={{ ...buttonStyle, fontSize: 11, height: 24, padding: "0 10px" }}
                            >
                              Copy snippet
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </Panel>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <Tweaks open={tweaks.open} onClose={() => tweaks.setOpen(false)} state={tweaks.state} set={tweaks.set} />
    </div>
  );
}

function BenchmarkBlock({
  label, median, min, max, extra, color,
}: {
  label: string; median: string; min: string; max: string; extra: string; color: string;
}) {
  return (
    <div style={{ border: `1px solid ${C.bd}`, background: C.bgCard, borderRadius: 4, padding: 14 }}>
      <div className="upper" style={{ color: C.dim }}>{label}</div>
      <div style={{
        fontFamily: "var(--font-serif)",
        fontSize: 28,
        fontWeight: 500,
        color,
        letterSpacing: "-0.02em",
        lineHeight: 1.05,
        marginTop: 6,
      }}>
        {median}
      </div>
      <div style={{ marginTop: 8, fontSize: 11, color: C.muted, fontFamily: "var(--font-jetbrains), monospace" }}>
        range: {min} – {max}
      </div>
      <div style={{ fontSize: 11, color: C.dim, fontFamily: "var(--font-jetbrains), monospace" }}>{extra}</div>
    </div>
  );
}
