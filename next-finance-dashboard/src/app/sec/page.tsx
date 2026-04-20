"use client";

import { useEffect, useState } from "react";
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
  EmptyState, Tweaks, useTweaks, StatPill,
} from "@/components/ui";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";
const SOURCE_HANDOFF_KEY = "sec-dashboard-source-handoff-v1";
const SEC_WORKBENCH_KEY = "sec-source-workbench-state-v1";

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

export default function SecDashboard() {
  const initialHandoff = (() => {
    if (typeof window === "undefined") return { search: "", category: "", minConf: "" };
    try {
      const handoff = window.localStorage.getItem(SOURCE_HANDOFF_KEY);
      if (!handoff) return { search: "", category: "", minConf: "" };
      const parsed = JSON.parse(handoff) as {
        route?: string; search?: string; category?: string; minConf?: string;
      };
      if (parsed.route !== "/sec") return { search: "", category: "", minConf: "" };
      window.localStorage.removeItem(SOURCE_HANDOFF_KEY);
      return { search: parsed.search || "", category: parsed.category || "", minConf: parsed.minConf || "" };
    } catch {
      return { search: "", category: "", minConf: "" };
    }
  })();
  const initialWorkbench = (() => {
    if (typeof window === "undefined") return { pinnedIds: [] as number[], selectedId: null as number | null };
    try {
      const saved = window.localStorage.getItem(SEC_WORKBENCH_KEY);
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

  const [contracts, setContracts] = useState<Contract[]>([]);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState(initialHandoff.search);
  const [category, setCategory] = useState(initialHandoff.category);
  const [minConf, setMinConf] = useState(initialHandoff.minConf);
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<number | null>(initialWorkbench.selectedId);
  const [pinnedIds, setPinnedIds] = useState<number[]>(initialWorkbench.pinnedIds);
  const [categories, setCategories] = useState<{ category: string; count: number }[]>([]);
  const [totalContracts, setTotalContracts] = useState(0);
  const [avgRoyalty, setAvgRoyalty] = useState<number | null>(null);
  const [avgConf, setAvgConf] = useState<number | null>(null);
  const [byYear, setByYear] = useState<{ year: number; count: number }[]>([]);
  const [byModel, setByModel] = useState<{ name: string; value: number }[]>([]);
  const [copied, setCopied] = useState<string | null>(null);

  const tweaks = useTweaks();

  useEffect(() => {
    fetch(`${API}/stats/`).then(r => r.json()).then(d => {
      setCategories(d.by_category || []);
      setTotalContracts(d.total_contracts || 0);
      setAvgRoyalty(d.avg_royalty_rate);
      setAvgConf(d.avg_confidence);
      setByYear(d.by_year || []);
      const model = d.by_model || {};
      setByModel(Object.entries(model).map(([k, v]) => ({ name: k, value: v as number })));
    }).catch(() => {});
  }, []);

  useEffect(() => {
    const p = new URLSearchParams({
      page: String(page), page_size: "25", sort: "confidence_score:desc", source: "EDGAR",
    });
    if (search) p.set("search", search);
    if (category) p.set("category", category);
    if (minConf) p.set("min_confidence", minConf);

    fetch(`${API}/contracts/?${p}`)
      .then(r => r.json())
      .then(d => { setContracts(d.data || []); setPagination(d.pagination); setLoading(false); })
      .catch(() => setLoading(false));
  }, [page, search, category, minConf]);

  useEffect(() => {
    try {
      window.localStorage.setItem(SEC_WORKBENCH_KEY, JSON.stringify({ pinnedIds, selectedId }));
    } catch {}
  }, [pinnedIds, selectedId]);

  const selected = selectedId != null
    ? contracts.find((c) => c.id === selectedId) || null
    : null;

  const pinnedContracts = pinnedIds
    .map((id) => contracts.find((c) => c.id === id) || (selected?.id === id ? selected : null))
    .filter((c): c is Contract => Boolean(c));

  const togglePin = (c: Contract) => {
    setPinnedIds((cur) => cur.includes(c.id) ? cur.filter((id) => id !== c.id) : [...cur, c.id].slice(-3));
  };

  const openEvidence = (url?: string | null) => {
    if (!url) return;
    window.open(url, "_blank", "noopener,noreferrer");
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

  const highConf = contracts.filter((c) => (c.confidence_score || 0) >= 0.8).length;

  return (
    <div className="app-shell">
      <AppNav />
      <div className="page-stack">
        <HealthStrip
          items={[
            { label: "SEC slice", labelKr: "SEC 슬라이스", value: fmtN(pagination?.total), tone: "muted" },
            { label: "Avg royalty", labelKr: "평균 로열티", value: avgRoyalty != null ? `${avgRoyalty.toFixed(1)}%` : "—", tone: "up" },
            { label: "Avg confidence", labelKr: "평균 신뢰도", value: avgConf != null ? `${(avgConf * 100).toFixed(0)}%` : "—", tone: "muted" },
            { label: "High conf", labelKr: "고신뢰", value: `${highConf} / ${contracts.length}`, tone: "up" },
            { label: "Pinned", labelKr: "핀 고정", value: String(pinnedIds.length), tone: pinnedIds.length > 0 ? "accent" : "muted" },
          ]}
        />

        {/* Page head */}
        <header style={{ marginTop: 22, marginBottom: 16 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 8 }}>
            <span className="upper" style={{ fontFamily: "var(--font-jetbrains), monospace", color: C.dim }}>
              SOURCE · SEC 10-K / EDGAR
            </span>
            <span style={{ flex: 1, borderTop: `1px solid ${C.bd}` }} />
            <span className="upper" style={{ fontFamily: "var(--font-jetbrains), monospace", color: C.dim }}>
              {fmtN(pagination?.total)} ROWS
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
            SEC <em style={{ fontStyle: "italic", color: C.accent }}>10-K</em> license agreements
          </h1>
          <p style={{ fontSize: 13, color: C.text2, maxWidth: 720, lineHeight: 1.65 }}>
            US disclosures extracted from annual reports — filter by category, confidence, or free text, then pin for comparison.
            <span style={{ display: "block", marginTop: 2, color: C.muted, fontSize: 12 }}>
              10-K 연차보고서에서 추출된 라이선스 계약. 분야 / 신뢰도 / 검색어로 필터링 후 비교 고정.
            </span>
          </p>
        </header>

        {/* KPIs */}
        <div className="kpi-grid">
          <KPI label="SEC Contracts" value={fmtN(pagination?.total)} color={C.sec} sub="EDGAR 10-K" />
          <KPI label="Total in DB" value={fmtN(totalContracts)} color={C.text} sub="All sources" />
          <KPI label="Avg Royalty" value={avgRoyalty != null ? `${avgRoyalty.toFixed(1)}%` : "—"} color={C.up} />
          <KPI label="Categories" value={fmtN(categories.length)} color={C.warn} />
        </div>

        {/* Charts */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 16, marginTop: 16 }}>
          <Panel title="Top categories" badge="분야">
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={categories.slice(0, 10)} margin={{ top: 8, right: 8, left: -16, bottom: 4 }}>
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

          <Panel title="Extraction model" badge="모델">
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={byModel.length > 0 ? byModel : [{ name: "—", value: 1 }]}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={70}
                  innerRadius={42}
                  strokeWidth={0}
                  label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}
                >
                  {byModel.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
              </PieChart>
            </ResponsiveContainer>
          </Panel>

          <Panel title="Year trend" badge="연도">
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={byYear} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                <defs>
                  <linearGradient id="secAreaGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={C.accent} stopOpacity={0.4} />
                    <stop offset="95%" stopColor={C.accent} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={C.bdSoft} />
                <XAxis dataKey="year" tick={{ fontSize: 10, fill: C.muted }} />
                <YAxis tick={{ fontSize: 10, fill: C.muted }} />
                <Tooltip contentStyle={tooltipStyle} />
                <Area type="monotone" dataKey="count" stroke={C.accent} fill="url(#secAreaGrad)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </Panel>
        </div>

        {/* Toolbar */}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 16, flexWrap: "wrap" }}>
          <button
            type="button"
            style={buttonStyle}
            onClick={() => copyText("SEC context", JSON.stringify({
              search, category, minConf, pinnedIds, selectedId, totalContracts,
            }, null, 2))}
          >
            Copy context
          </button>
          <button type="button" style={buttonStyle} onClick={() => tweaks.setOpen(true)}>Tweaks</button>
          {copied && <StatPill label="Clipboard" value={copied} color={copied.includes("failed") ? C.accent : C.up} />}
        </div>

        {/* Main grid */}
        <div className="workbench-grid" style={{ marginTop: 16 }}>
          <aside>
            <Panel title="Filters" badge="필터">
              <FilterField label="Search">
                <input value={search} onChange={(e) => { setPage(1); setSearch(e.target.value); }} style={inputStyle} placeholder="company, tech…" />
              </FilterField>
              <FilterField label="Category">
                <select value={category} onChange={(e) => { setPage(1); setCategory(e.target.value); }} style={selectStyle}>
                  <option value="">All</option>
                  {categories.slice(0, 30).map(c => <option key={c.category} value={c.category}>{c.category} ({c.count})</option>)}
                </select>
              </FilterField>
              <FilterField label="Min Confidence">
                <select value={minConf} onChange={(e) => { setPage(1); setMinConf(e.target.value); }} style={selectStyle}>
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
                Reset
              </button>
            </Panel>
          </aside>

          <div>
            <CompareTray
              items={pinnedContracts.map((c) => ({
                id: c.id,
                title: c.company_name || c.tech_name || `Contract ${c.id}`,
                meta: `SEC · ${c.tech_category || "—"} · ${c.filing_year || "—"} · ${fmtPct(c.royalty_rate)}`,
                tone: C.sec,
              }))}
              selectedId={selectedId}
              onSelect={(id) => {
                const next = pinnedContracts.find((c) => c.id === id) || contracts.find((c) => c.id === id) || null;
                setSelectedId(next?.id ?? null);
              }}
              onRemove={(id) => setPinnedIds((cur) => cur.filter((v) => v !== id))}
            />

            <Panel title="EDGAR comparables grid" badge="비교표">
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5, minWidth: 960 }}>
                  <thead>
                    <tr style={{ fontSize: 10.5, textTransform: "uppercase", letterSpacing: "0.08em", color: C.dim }}>
                      {["Company", "Ticker", "Licensor", "Technology", "Category", "Royalty", "Upfront", "Year", "Conf"].map((h, i) => (
                        <th
                          key={h}
                          style={{
                            padding: "8px 10px",
                            textAlign: i >= 5 && i <= 7 ? "right" : i === 8 ? "center" : "left",
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
                    {loading && (
                      <tr><td colSpan={9} style={{ padding: "48px 0", textAlign: "center", color: C.dim }}>Loading…</td></tr>
                    )}
                    {!loading && contracts.length === 0 && (
                      <tr><td colSpan={9}><EmptyState message="No data for current filters" /></td></tr>
                    )}
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
                            height: "var(--row-h)",
                          }}
                        >
                          <td style={{ padding: "var(--pad-cell) 10px", fontWeight: 500 }}>
                            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                              <span>{c.company_name || "—"}</span>
                              <button
                                type="button"
                                onClick={(e) => { e.stopPropagation(); togglePin(c); }}
                                aria-label={pinned ? "Unpin" : "Pin"}
                                style={{
                                  width: 20, height: 20, padding: 0, border: "none", background: "transparent",
                                  color: pinned ? C.accent : C.dim, cursor: "pointer", fontSize: 14, lineHeight: 1,
                                }}
                              >
                                ◆
                              </button>
                            </div>
                          </td>
                          <td style={{ padding: "var(--pad-cell) 10px", fontFamily: "var(--font-jetbrains), monospace", fontSize: 11, color: C.text2 }}>
                            {c.ticker || "—"}
                          </td>
                          <td style={{ padding: "var(--pad-cell) 10px", color: C.text2 }}>{c.licensor_name || "—"}</td>
                          <td
                            style={{
                              padding: "var(--pad-cell) 10px",
                              color: C.text2,
                              maxWidth: 180,
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                            }}
                            title={c.tech_name || undefined}
                          >
                            {c.tech_name || "—"}
                          </td>
                          <td style={{ padding: "var(--pad-cell) 10px" }}>
                            {c.tech_category ? (
                              <span
                                style={{
                                  background: C.accentSoft,
                                  color: C.accentHover,
                                  padding: "1px 7px",
                                  borderRadius: 2,
                                  fontSize: 10.5,
                                  fontFamily: "var(--font-jetbrains), monospace",
                                }}
                              >
                                {c.tech_category}
                              </span>
                            ) : "—"}
                          </td>
                          <td style={{ padding: "var(--pad-cell) 10px", textAlign: "right", fontFamily: "var(--font-jetbrains), monospace", color: c.royalty_rate != null ? C.up : C.dim }}>
                            {fmtPct(c.royalty_rate)}
                          </td>
                          <td style={{ padding: "var(--pad-cell) 10px", textAlign: "right", fontFamily: "var(--font-jetbrains), monospace", color: C.text2 }}>
                            {fmtMoney(c.upfront_amount)}
                          </td>
                          <td style={{ padding: "var(--pad-cell) 10px", textAlign: "center", fontFamily: "var(--font-jetbrains), monospace", color: C.text2 }}>
                            {c.filing_year || "—"}
                          </td>
                          <td style={{ padding: "var(--pad-cell) 10px" }}>
                            <ConfBar value={c.confidence_score || 0} />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Panel>

            {pagination && (
              <div style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginTop: 14,
                paddingTop: 14,
                borderTop: `1px solid ${C.bd}`,
                fontSize: 12,
                color: C.muted,
              }}>
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
                      <SourceBadge source={selected.source_system} />
                      {selected.accession_number && <SourceChip src="sec" form="10-K" code={selected.accession_number} />}
                    </div>
                    <h3 style={{
                      marginTop: 8, marginBottom: 2,
                      fontFamily: "var(--font-serif)", fontSize: 18, fontWeight: 500, letterSpacing: "-0.01em",
                    }}>
                      {selected.company_name || "Unknown"}
                    </h3>
                    <div style={{ fontSize: 12, color: C.text2 }}>
                      {selected.ticker || "—"} · {selected.filing_year || "—"}
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
                    <DRow label="Filing ref" value={selected.accession_number || selected.rcept_no} />
                    <DRow label="Filing date" value={selected.filing_date} />
                  </DetailBox>

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
                        id: selected.id, source: selected.source_system,
                        company: selected.company_name, ticker: selected.ticker,
                        licensor: selected.licensor_name, licensee: selected.licensee_name,
                        technology: selected.tech_name, category: selected.tech_category,
                        royalty_rate: selected.royalty_rate, upfront_amount: selected.upfront_amount,
                        term_years: selected.term_years, territory: selected.territory,
                        confidence_score: selected.confidence_score, filing_year: selected.filing_year,
                        extraction_model: selected.extraction_model,
                        accession_number: selected.accession_number, filing_date: selected.filing_date,
                        source_url: selected.source_url,
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
      </div>

      <Tweaks open={tweaks.open} onClose={() => tweaks.setOpen(false)} state={tweaks.state} set={tweaks.set} />
    </div>
  );
}
