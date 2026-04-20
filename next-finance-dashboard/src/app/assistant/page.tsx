"use client";

import { useEffect, useMemo, useState } from "react";
import { AppNav } from "@/components/app-nav";
import { C, buttonStyle } from "@/components/theme";
import {
  CompareTray, DetailBox, DRow, EmptyState, HealthStrip, InlineError,
  SourceCompareCard, StatPill, Panel, Quote, EvidenceCard, SourceChip,
  SourceBadge, Tweaks, useTweaks,
} from "@/components/ui";

const STORAGE_KEY = "sec-assistant-workbench-state-v1";
const DASHBOARD_HANDOFF_KEY = "sec-assistant-dashboard-handoff-v1";
const SOURCE_HANDOFF_KEY = "sec-dashboard-source-handoff-v1";

type ContractResult = {
  id: number;
  licensor: string | null;
  licensee: string | null;
  tech_name: string | null;
  category: string | null;
  royalty_rate: number | null;
  upfront_amount: number | null;
  term_years: number | null;
  territory: string | null;
  confidence: number | null;
  company: string | null;
  year: number | null;
  source: string | null;
  accession_number: string | null;
  rcept_no: string | null;
  filing_date: string | null;
  source_url: string | null;
};

type SearchSuggestion = { keywords: string[]; categories: string[]; reasoning: string };
type MarketRange = {
  royalty?:   { min: number; max: number; median: number; count: number };
  upfront?:   { min: number; max: number; median: number; count: number };
  term_years?:{ min: number; max: number; median: number; count: number };
};
type AnalysisResult = { summary: string; market_range: MarketRange | null; recommendation: string };
type AssistantResponse = {
  search_suggestions: SearchSuggestion;
  contracts: ContractResult[];
  analysis: AnalysisResult;
  rag_context_used: boolean;
};

const EXAMPLE_QUERIES = [
  { q: "Chemical manufacturing royalty benchmarks for process technology", kr: "화학 공정기술 로열티 벤치마크" },
  { q: "Semiconductor process licensing deal comps",                        kr: "반도체 공정 라이선스 계약 비교" },
  { q: "Pharmaceutical drug licensing royalty rates",                       kr: "의약품 라이선스 로열티" },
  { q: "Display materials cross-border licensing terms",                    kr: "디스플레이 재료 크로스보더 계약" },
  { q: "Software patent licensing terms and conditions",                    kr: "소프트웨어 특허 라이선스 조건" },
];

const fmtMoney = (v: number | null | undefined): string => {
  if (v == null) return "—";
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `$${(v / 1e3).toFixed(0)}K`;
  return `$${v.toLocaleString()}`;
};

const confColor = (v: number): string => {
  if (v >= 0.8) return C.up;
  if (v >= 0.6) return C.warn;
  if (v >= 0.4) return "#b97e34";
  return C.accent;
};

function contractTitle(c: ContractResult) {
  return c.company || c.licensor || c.tech_name || `Contract ${c.id}`;
}

export default function AssistantPage() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [result, setResult] = useState<AssistantResponse | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [pinnedIds, setPinnedIds] = useState<number[]>([]);

  const tweaks = useTweaks();

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (!saved) return;
      const parsed = JSON.parse(saved) as {
        query?: string; result?: AssistantResponse | null;
        expandedId?: number | null; pinnedIds?: number[];
      };
      if (parsed.query) setQuery(parsed.query);
      if (parsed.result) setResult(parsed.result);
      if (typeof parsed.expandedId === "number") setExpandedId(parsed.expandedId);
      if (Array.isArray(parsed.pinnedIds))
        setPinnedIds(parsed.pinnedIds.filter((id) => typeof id === "number").slice(0, 3));
    } catch {}
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ query, result, expandedId, pinnedIds }));
    } catch {}
  }, [query, result, expandedId, pinnedIds]);

  const handleSubmit = async (q?: string) => {
    const question = q || query;
    if (!question.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);
    setExpandedId(null);
    setPinnedIds([]);

    try {
      const res = await fetch("/api/assistant", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, max_results: 15 }),
      });
      if (!res.ok) throw new Error(`API ${res.status}`);
      setResult((await res.json()) as AssistantResponse);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const pinnedContracts = useMemo(
    () => (result?.contracts || []).filter((c) => pinnedIds.includes(c.id)),
    [result, pinnedIds]
  );

  const selectedContract = useMemo(
    () => (result?.contracts || []).find((c) => c.id === expandedId) || null,
    [result, expandedId]
  );

  const togglePin = (id: number) => {
    setPinnedIds((cur) => cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id].slice(-3));
  };

  const pushToDashboard = (contract?: ContractResult | null) => {
    try {
      const searchSeed = contract?.company || contract?.licensor || contract?.tech_name || query;
      window.localStorage.setItem(DASHBOARD_HANDOFF_KEY, JSON.stringify({
        search: searchSeed || "", category: contract?.category || "", source: "",
      }));
    } catch {}
    window.location.href = "/";
  };

  const pushToSourceWorkbench = (contract: ContractResult) => {
    const route = contract.source === "DART" ? "/dart" : "/sec";
    try {
      window.localStorage.setItem(SOURCE_HANDOFF_KEY, JSON.stringify({
        route,
        search: contract.company || contract.licensor || contract.tech_name || query,
        category: contract.category || "",
        minConf: contract.confidence != null ? String(Math.max(0.4, Math.floor(contract.confidence * 10) / 10)) : "",
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

  const resultHealth: "up" | "warn" | "cyan" | "muted" = result
    ? result.contracts.length === 0 ? "warn" : "up"
    : loading ? "cyan" : "muted";

  return (
    <div className="app-shell">
      <AppNav />

      <div className="page-stack">
        <HealthStrip
          items={[
            {
              label: "Assistant",
              labelKr: "어시스턴트",
              value: loading ? "Running" : result ? (result.contracts.length === 0 ? "No match" : "Ready") : "Idle",
              tone: resultHealth,
            },
            { label: "Results", labelKr: "결과 수", value: result ? String(result.contracts.length) : "—", tone: "muted" },
            { label: "Pinned", labelKr: "핀 고정", value: String(pinnedIds.length), tone: pinnedIds.length > 0 ? "accent" : "muted" },
            { label: "RAG", labelKr: "컨텍스트", value: result?.rag_context_used ? "Enabled" : "Off", tone: result?.rag_context_used ? "up" : "muted" },
            { label: "Language", labelKr: "언어", value: "EN · KR", tone: "muted" },
          ]}
        />

        {/* Page head */}
        <header style={{ marginTop: 22, marginBottom: 14 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 8 }}>
            <span className="upper" style={{ fontFamily: "var(--font-jetbrains), monospace", color: C.dim }}>
              ASSISTANT · RESEARCH COPILOT
            </span>
            <span style={{ flex: 1, borderTop: `1px solid ${C.bd}` }} />
            <span className="upper" style={{ fontFamily: "var(--font-jetbrains), monospace", color: C.dim }}>
              {result ? "EVIDENCE + STRATEGY" : "ASK"}
            </span>
          </div>
          <h1 style={{
            fontFamily: "var(--font-serif)",
            fontSize: 32,
            fontWeight: 500,
            letterSpacing: "-0.02em",
            margin: "0 0 8px",
            lineHeight: 1.1,
          }}>
            Ask in plain language. Get <em style={{ fontStyle: "italic", color: C.accent }}>citation-backed</em> comparables.
          </h1>
          <p style={{ fontSize: 13, color: C.text2, maxWidth: 760, lineHeight: 1.65 }}>
            Describe the licensing situation; the assistant returns search strategy, matching contracts, and a market range.
            Pin 2–3 for side-by-side inspection or jump to the source workbench for deeper drill-down.
            <span style={{ display: "block", marginTop: 2, color: C.muted, fontSize: 12 }}>
              자연어로 상황을 설명하면 검색 전략·유사 계약·시장 범위가 돌아옵니다. 핀 후 비교하거나 원천 워크벤치로 이동하세요.
            </span>
          </p>
        </header>

        {/* Composer */}
        <div
          style={{
            border: `1px solid ${C.bd}`,
            background: C.bgCard,
            borderRadius: 4,
            padding: 14,
          }}
        >
          <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) auto", gap: 10 }}>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
              placeholder="Describe the licensing situation you want comparable evidence for…"
              style={{
                width: "100%",
                padding: "10px 12px",
                borderRadius: 4,
                border: `1px solid ${C.bd}`,
                background: C.bgInput,
                color: C.text,
                fontSize: 14,
                outline: "none",
                fontFamily: "inherit",
              }}
              disabled={loading}
            />
            <button
              onClick={() => handleSubmit()}
              disabled={loading || !query.trim()}
              style={{
                ...buttonStyle,
                background: loading || !query.trim() ? C.bgCard : C.text,
                color: loading || !query.trim() ? C.muted : C.bg,
                borderColor: loading || !query.trim() ? C.bd : C.text,
                padding: "0 18px",
                height: 38,
                opacity: loading || !query.trim() ? 0.65 : 1,
              }}
            >
              {loading ? "Analyzing…" : "Run search"}
            </button>
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
            <button type="button" onClick={() => pushToDashboard(null)} style={buttonStyle}>
              Open in unified dashboard
            </button>
            <button type="button" onClick={() => copyText("Search seed", query)} disabled={!query.trim()} style={{ ...buttonStyle, opacity: query.trim() ? 1 : 0.5 }}>
              Copy search seed
            </button>
            <button type="button" onClick={() => tweaks.setOpen(true)} style={buttonStyle}>Tweaks</button>
            {copied && <StatPill label="Clipboard" value={copied} color={copied.includes("failed") ? C.accent : C.up} />}
          </div>
          {!result && !loading && (
            <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
              {EXAMPLE_QUERIES.map((ex, i) => (
                <button
                  key={i}
                  onClick={() => { setQuery(ex.q); handleSubmit(ex.q); }}
                  style={{
                    border: `1px solid ${C.bd}`,
                    background: C.bgCard,
                    padding: "6px 10px",
                    borderRadius: 999,
                    fontSize: 11.5,
                    color: C.text2,
                    cursor: "pointer",
                    fontFamily: "inherit",
                  }}
                >
                  {ex.q}
                  <span className="kr" style={{ marginLeft: 6 }}>· {ex.kr}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {error && <div style={{ marginTop: 16 }}><InlineError title="Assistant request failed" message={`${error}. Check backend availability.`} /></div>}

        {loading && (
          <div style={{ marginTop: 16, padding: 24, border: `1px solid ${C.bd}`, background: C.bgCard, borderRadius: 4 }}>
            <div className="upper" style={{ color: C.dim, marginBottom: 10 }}>Running · 분석 중</div>
            <div className="skeleton" style={{ height: 16, width: "48%", marginBottom: 10 }} />
            <div className="skeleton" style={{ height: 12, width: "100%", marginBottom: 6 }} />
            <div className="skeleton" style={{ height: 12, width: "88%", marginBottom: 6 }} />
            <div className="skeleton" style={{ height: 12, width: "72%" }} />
          </div>
        )}

        {result && !loading && (
          <>
            <div className="source-card-grid" style={{ marginTop: 18 }}>
              <SourceCompareCard
                label="Matches"
                value={String(result.contracts.length)}
                sub="candidates"
                meta="Direct evidence returned by the query"
                tone={C.accent}
                active
              />
              <SourceCompareCard
                label="Keywords"
                value={String(result.search_suggestions.keywords.length)}
                sub="tokens"
                meta={result.search_suggestions.keywords.slice(0, 3).join(" · ") || "—"}
                tone={C.sec}
              />
              <SourceCompareCard
                label="Categories"
                value={String(result.search_suggestions.categories.length)}
                sub="hints"
                meta={result.search_suggestions.categories.slice(0, 3).join(" · ") || "—"}
                tone={C.dart}
              />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "260px minmax(0, 1fr) 340px", gap: 20, marginTop: 18, alignItems: "start" }}>
              {/* Strategy */}
              <aside>
                <Panel title="Query strategy" badge="검색 전략">
                  <div style={{ display: "grid", gap: 14 }}>
                    <div>
                      <div className="upper" style={{ color: C.dim, marginBottom: 6 }}>Reasoning</div>
                      <p style={{ fontFamily: "var(--font-serif)", fontSize: 13, color: C.text, lineHeight: 1.6, margin: 0 }}>
                        {result.search_suggestions.reasoning}
                      </p>
                      <div style={{ display: "flex", gap: 6, marginTop: 10, flexWrap: "wrap" }}>
                        <button type="button" onClick={() => copyText("Strategy", result.search_suggestions.reasoning)} style={{ ...buttonStyle, fontSize: 11, height: 24, padding: "0 10px" }}>
                          Copy strategy
                        </button>
                        <button
                          type="button"
                          onClick={() => copyText("Comparable context", JSON.stringify({
                            query,
                            keywords: result.search_suggestions.keywords,
                            categories: result.search_suggestions.categories,
                            recommendation: result.analysis.recommendation,
                          }, null, 2))}
                          style={{ ...buttonStyle, fontSize: 11, height: 24, padding: "0 10px" }}
                        >
                          Copy context
                        </button>
                      </div>
                    </div>
                    <div>
                      <div className="upper" style={{ color: C.dim, marginBottom: 6 }}>Keywords</div>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                        {result.search_suggestions.keywords.map((k) => (
                          <StatPill key={k} label="KW" value={k} color={C.accent} />
                        ))}
                      </div>
                    </div>
                    <div>
                      <div className="upper" style={{ color: C.dim, marginBottom: 6 }}>Categories</div>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                        {result.search_suggestions.categories.map((cat) => (
                          <StatPill key={cat} label="CAT" value={cat} color={C.warn} />
                        ))}
                      </div>
                    </div>
                  </div>
                </Panel>
              </aside>

              {/* Main: analysis + contracts */}
              <section>
                <CompareTray
                  items={pinnedContracts.map((c) => ({
                    id: c.id,
                    title: contractTitle(c),
                    meta: `${c.category || "—"} · ${c.year || "—"} · ${c.royalty_rate != null ? `${c.royalty_rate}%` : "—"}`,
                    tone: confColor(c.confidence || 0),
                  }))}
                  selectedId={expandedId}
                  onSelect={(id) => setExpandedId(id)}
                  onRemove={(id) => setPinnedIds((cur) => cur.filter((v) => v !== id))}
                />

                <Panel title="AI analysis" badge="AI 분석">
                  <p style={{ fontFamily: "var(--font-serif)", fontSize: 14, color: C.text, lineHeight: 1.65, margin: 0 }}>
                    {result.analysis.summary}
                  </p>
                  <div style={{ marginTop: 14, borderLeft: `2px solid ${C.accent}`, paddingLeft: 14 }}>
                    <div className="upper" style={{ color: C.accent, marginBottom: 4 }}>Recommendation · 권고</div>
                    <p style={{ fontFamily: "var(--font-serif)", fontSize: 13, color: C.text, lineHeight: 1.6, margin: 0 }}>
                      {result.analysis.recommendation}
                    </p>
                  </div>
                </Panel>

                <div style={{ marginTop: 16 }}>
                  <Panel title={`Matching contracts · ${result.contracts.length}`} badge="유사 계약">
                    {result.contracts.length === 0 ? (
                      <EmptyState message="No matching contracts. Try a more specific context or different keywords." />
                    ) : (
                      <div style={{ display: "grid", gap: 10 }}>
                        {result.contracts.map((c) => {
                          const isOpen = expandedId === c.id;
                          const conf = c.confidence || 0;
                          const pinned = pinnedIds.includes(c.id);
                          return (
                            <article
                              key={c.id}
                              style={{
                                borderTop: `1px solid ${isOpen ? C.accent : C.bd}`,
                                borderRight: `1px solid ${isOpen ? C.accent : C.bd}`,
                                borderBottom: `1px solid ${isOpen ? C.accent : C.bd}`,
                                borderLeft: `3px solid ${confColor(conf)}`,
                                background: isOpen ? C.accentSoft : C.bgCard,
                                padding: 14,
                                borderRadius: 4,
                              }}
                            >
                              <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
                                <div
                                  style={{
                                    width: 38,
                                    height: 38,
                                    borderRadius: 2,
                                    background: confColor(conf),
                                    color: "#fff",
                                    display: "grid",
                                    placeItems: "center",
                                    fontSize: 12,
                                    fontWeight: 700,
                                    fontFamily: "var(--font-jetbrains), monospace",
                                    flexShrink: 0,
                                  }}
                                >
                                  {(conf * 100).toFixed(0)}
                                </div>
                                <div style={{ minWidth: 0, flex: 1 }}>
                                  <div style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "flex-start" }}>
                                    <div>
                                      <div
                                        style={{
                                          fontFamily: "var(--font-serif)",
                                          fontSize: 15,
                                          fontWeight: 500,
                                          letterSpacing: "-0.01em",
                                        }}
                                      >
                                        {c.licensor || "—"}{" "}
                                        <span style={{ color: C.muted, fontStyle: "italic", fontWeight: 400 }}>→</span>{" "}
                                        {c.licensee || "—"}
                                      </div>
                                      <div style={{ marginTop: 4, fontSize: 12, color: C.text2 }}>
                                        {c.tech_name || "Technology not extracted"}
                                      </div>
                                    </div>
                                    <button
                                      type="button"
                                      onClick={() => togglePin(c.id)}
                                      style={{
                                        ...buttonStyle,
                                        padding: "0 10px",
                                        height: 24,
                                        fontSize: 11,
                                        background: pinned ? C.accentSoft : C.bgCard,
                                        color: pinned ? C.accent : C.text,
                                        borderColor: pinned ? C.accent : C.bd,
                                      }}
                                    >
                                      {pinned ? "Pinned" : "Pin"}
                                    </button>
                                  </div>
                                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10 }}>
                                    <SourceBadge source={c.source} />
                                    {c.source === "EDGAR" && c.accession_number && <SourceChip src="sec" code={c.accession_number} />}
                                    {c.source === "DART" && c.rcept_no && <SourceChip src="dart" code={c.rcept_no} />}
                                    {c.category && <StatPill label="Cat" value={c.category} color={C.accent} />}
                                    {c.year && <StatPill label="Year" value={String(c.year)} />}
                                    {c.royalty_rate != null && <StatPill label="Royalty" value={`${c.royalty_rate}%`} color={C.up} />}
                                    {c.upfront_amount != null && c.upfront_amount > 0 && <StatPill label="Upfront" value={fmtMoney(c.upfront_amount)} color={C.warn} />}
                                    {c.term_years != null && <StatPill label="Term" value={`${c.term_years}y`} />}
                                  </div>
                                  <div style={{ display: "flex", gap: 6, marginTop: 10, flexWrap: "wrap" }}>
                                    <button type="button" onClick={() => setExpandedId(isOpen ? null : c.id)} style={{ ...buttonStyle, fontSize: 11, height: 24, padding: "0 10px" }}>
                                      {isOpen ? "Hide" : "Inspect"}
                                    </button>
                                    <button type="button" onClick={() => pushToDashboard(c)} style={{ ...buttonStyle, fontSize: 11, height: 24, padding: "0 10px" }}>
                                      Send to dashboard
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => copyText("Contract context", JSON.stringify({
                                        company: c.company, licensor: c.licensor, licensee: c.licensee,
                                        technology: c.tech_name, category: c.category,
                                        royalty_rate: c.royalty_rate, upfront_amount: c.upfront_amount,
                                        term_years: c.term_years, territory: c.territory,
                                        confidence: c.confidence, year: c.year, source: c.source,
                                        accession_number: c.accession_number, rcept_no: c.rcept_no,
                                        filing_date: c.filing_date, source_url: c.source_url,
                                      }, null, 2))}
                                      style={{ ...buttonStyle, fontSize: 11, height: 24, padding: "0 10px" }}
                                    >
                                      Copy
                                    </button>
                                    {c.source_url && (
                                      <button type="button" onClick={() => openEvidence(c.source_url)} style={{ ...buttonStyle, fontSize: 11, height: 24, padding: "0 10px" }}>
                                        Filing
                                      </button>
                                    )}
                                    <button type="button" onClick={() => pushToSourceWorkbench(c)} style={{ ...buttonStyle, fontSize: 11, height: 24, padding: "0 10px" }}>
                                      Open source
                                    </button>
                                  </div>
                                </div>
                              </div>
                            </article>
                          );
                        })}
                      </div>
                    )}
                  </Panel>
                </div>
              </section>

              {/* Inspection rail */}
              <aside style={{ display: "grid", gap: 14, position: "sticky", top: 80, alignSelf: "start" }}>
                <Panel title="Market range" badge="시장 범위">
                  {result.analysis.market_range ? (
                    <div style={{ display: "grid", gap: 10 }}>
                      {result.analysis.market_range.royalty && (
                        <RangeRow
                          label="Royalty"
                          min={`${result.analysis.market_range.royalty.min}%`}
                          max={`${result.analysis.market_range.royalty.max}%`}
                          median={`${result.analysis.market_range.royalty.median}%`}
                          count={result.analysis.market_range.royalty.count}
                          color={C.accent}
                        />
                      )}
                      {result.analysis.market_range.upfront && (
                        <RangeRow
                          label="Upfront"
                          min={fmtMoney(result.analysis.market_range.upfront.min)}
                          max={fmtMoney(result.analysis.market_range.upfront.max)}
                          median={fmtMoney(result.analysis.market_range.upfront.median)}
                          count={result.analysis.market_range.upfront.count}
                          color={C.warn}
                        />
                      )}
                      {result.analysis.market_range.term_years && (
                        <RangeRow
                          label="Term"
                          min={`${result.analysis.market_range.term_years.min}y`}
                          max={`${result.analysis.market_range.term_years.max}y`}
                          median={`${result.analysis.market_range.term_years.median}y`}
                          count={result.analysis.market_range.term_years.count}
                          color={C.up}
                        />
                      )}
                    </div>
                  ) : (
                    <EmptyState message="No market range for this query." />
                  )}
                </Panel>

                {selectedContract ? (
                  <>
                    <DetailBox title="Selected contract">
                      <DRow label="Company" value={selectedContract.company} />
                      <DRow label="Licensor" value={selectedContract.licensor} />
                      <DRow label="Licensee" value={selectedContract.licensee} />
                      <DRow label="Category" value={selectedContract.category} />
                    </DetailBox>
                    <DetailBox title="Economics">
                      <DRow label="Royalty" value={selectedContract.royalty_rate != null ? `${selectedContract.royalty_rate}%` : null} highlight />
                      <DRow label="Upfront" value={selectedContract.upfront_amount != null ? fmtMoney(selectedContract.upfront_amount) : null} />
                      <DRow label="Term" value={selectedContract.term_years != null ? `${selectedContract.term_years}y` : null} />
                      <DRow label="Territory" value={selectedContract.territory} />
                    </DetailBox>
                    <DetailBox title="Trust">
                      <DRow label="Confidence" value={`${((selectedContract.confidence || 0) * 100).toFixed(0)}%`} />
                      <DRow label="Year" value={selectedContract.year?.toString()} />
                      <DRow label="Source mode" value={result.rag_context_used ? "RAG-assisted" : "Direct"} />
                      <DRow label="Source system" value={selectedContract.source} />
                      <DRow label="Filing ref" value={selectedContract.accession_number || selectedContract.rcept_no} />
                      <DRow label="Filing date" value={selectedContract.filing_date} />
                    </DetailBox>
                    <div style={{ display: "grid", gap: 6 }}>
                      {selectedContract.source_url && (
                        <button type="button" onClick={() => openEvidence(selectedContract.source_url)} style={{ ...buttonStyle, width: "100%", justifyContent: "center" }}>
                          Open filing evidence
                        </button>
                      )}
                      <button type="button" onClick={() => pushToSourceWorkbench(selectedContract)} style={{ ...buttonStyle, width: "100%", justifyContent: "center", background: C.text, color: C.bg, borderColor: C.text }}>
                        Open source workbench
                      </button>
                    </div>
                  </>
                ) : (
                  <Panel title="Inspection" badge="선택 없음">
                    <EmptyState message="Inspect a contract to review its economics and trust signals here." />
                  </Panel>
                )}

                <Panel title="Evidence rail" badge="증거">
                  {(result.contracts.slice(0, 3)).map((c) => (
                    <EvidenceCard
                      key={c.id}
                      title={contractTitle(c)}
                      meta={`${c.source || "—"} · ${c.year || "—"} · conf ${((c.confidence || 0) * 100).toFixed(0)}%`}
                      snippet={c.tech_name || "—"}
                      onClick={() => setExpandedId(c.id)}
                    />
                  ))}
                </Panel>
              </aside>
            </div>
          </>
        )}

        {!result && !loading && !error && (
          <div style={{ marginTop: 24 }}>
            <Quote
              text="This assistant reads the SEC+DART corpus, suggests a search strategy, returns matching contracts with <em style='color:inherit'>provenance chips</em>, and computes a market range."
              cite="License Intelligence · assistant"
            />
          </div>
        )}
      </div>

      <Tweaks open={tweaks.open} onClose={() => tweaks.setOpen(false)} state={tweaks.state} set={tweaks.set} />
    </div>
  );
}

function RangeRow({
  label, min, max, median, count, color,
}: {
  label: string; min: string; max: string; median: string; count: number; color: string;
}) {
  return (
    <div
      style={{
        border: `1px solid ${C.bd}`,
        background: C.bgCard,
        padding: 10,
        borderRadius: 4,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span className="upper" style={{ color: C.dim }}>{label}</span>
        <span style={{ fontFamily: "var(--font-jetbrains), monospace", fontSize: 10.5, color: C.dim }}>
          n={count}
        </span>
      </div>
      <div style={{ marginTop: 8, display: "flex", justifyContent: "space-between", alignItems: "flex-end", gap: 10 }}>
        <span style={{ fontSize: 11, color: C.muted, fontFamily: "var(--font-jetbrains), monospace" }}>{min}</span>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontFamily: "var(--font-serif)", fontSize: 20, fontWeight: 500, color, letterSpacing: "-0.02em" }}>
            {median}
          </div>
          <div style={{ fontSize: 10, color: C.dim, textTransform: "uppercase", letterSpacing: "0.08em" }}>median</div>
        </div>
        <span style={{ fontSize: 11, color: C.muted, fontFamily: "var(--font-jetbrains), monospace" }}>{max}</span>
      </div>
      <div style={{ marginTop: 8, height: 4, background: C.bgEl, overflow: "hidden", borderRadius: 1 }}>
        <div style={{ width: "60%", height: "100%", background: color }} />
      </div>
    </div>
  );
}
