"use client";

import { useEffect, useMemo, useState } from "react";
import { AppNav } from "@/components/app-nav";

type Row = {
  company?: string;
  ticker?: string;
  cik?: string;
  licensor_name?: string;
  licensee_name?: string;
  tech_name?: string;
  tech_category?: string;
  industry?: string;
  filing_year?: number | string | null;
  confidence?: number | string | null;
  royalty_rate?: number | string | null;
  royalty_unit?: string | null;
  upfront_amount?: number | string | null;
  upfront_currency?: string | null;
  territory?: string | string[] | null;
  term_years?: number | string | null;
  reasoning?: string | null;
};

type Metrics = {
  agreements: number;
  companies: number;
  bothFinancialTerms: number;
  avgRoyaltyRate: number | null;
};

type ApiResponse = {
  meta: {
    scanTimestamp: string | null;
    totalLicenseFiles: number;
    scanErrors: number;
  };
  overall: Metrics;
  filtered: Metrics;
  charts: {
    filtered: {
      topCategories: Array<{ key: string; label: string; count: number }>;
    };
  };
  pagination: {
    page: number;
    pageSize: number;
    total: number;
    totalPages: number;
  };
  rows: Row[];
};

const PAGE_SIZE = 20;
const SORT_OPTIONS = [
  { key: "confidence_desc", label: "Confidence (High)", spec: "confidence:desc" },
  { key: "confidence_asc", label: "Confidence (Low)", spec: "confidence:asc" },
  { key: "year_desc", label: "Year (Newest)", spec: "filing_year:desc,confidence:desc" },
  { key: "year_asc", label: "Year (Oldest)", spec: "filing_year:asc,confidence:desc" },
  { key: "royalty_desc", label: "Royalty (Highest)", spec: "royalty_rate:desc,confidence:desc" },
  { key: "upfront_desc", label: "Upfront (Highest)", spec: "upfront_amount:desc,confidence:desc" },
] as const;

function fmtPct(v: unknown): string {
  if (v === null || v === undefined || String(v).trim() === "") return "-";
  const n = Number(v);
  return Number.isFinite(n) ? `${n.toFixed(2)}%` : "-";
}

function fmtMoney(v: unknown, ccy?: string | null): string {
  if (v === null || v === undefined || String(v).trim() === "") return "-";
  const n = Number(v);
  if (!Number.isFinite(n)) return "-";
  const prefix = ccy || "$";
  if (n >= 1e9) return `${prefix}${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${prefix}${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${prefix}${(n / 1e3).toFixed(0)}K`;
  return `${prefix}${n.toLocaleString()}`;
}

function fmtTerritory(v: unknown): string {
  if (!v) return "-";
  if (Array.isArray(v)) return v.join(", ");
  return String(v);
}

function confColor(v: number): string {
  if (v >= 0.8) return "#16a34a";
  if (v >= 0.6) return "#ca8a04";
  if (v >= 0.4) return "#ea580c";
  return "#dc2626";
}

function confLabel(v: number): string {
  if (v >= 0.8) return "High";
  if (v >= 0.6) return "Medium";
  if (v >= 0.4) return "Low";
  return "Very Low";
}

export default function SecPrototypePage() {
  const [data, setData] = useState<ApiResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  const [search, setSearch] = useState("");
  const [minConfidence, setMinConfidence] = useState("");
  const [onlyFinancialTerms, setOnlyFinancialTerms] = useState(false);
  const [sortOption, setSortOption] = useState<(typeof SORT_OPTIONS)[number]["key"]>("confidence_desc");
  const [page, setPage] = useState(1);

  // Debug panels
  const [showApiPath, setShowApiPath] = useState(false);
  const [showJsonSample, setShowJsonSample] = useState(false);

  const sortSpec = useMemo(() => {
    const selected = SORT_OPTIONS.find((item) => item.key === sortOption);
    return selected?.spec ?? SORT_OPTIONS[0].spec;
  }, [sortOption]);

  const requestPath = useMemo(() => {
    const sp = new URLSearchParams({
      page: String(page),
      pageSize: String(PAGE_SIZE),
      sort: sortSpec,
      search,
      minConfidence,
      excludeMissingRoyalty: onlyFinancialTerms ? "1" : "0",
      excludeMissingUpfront: onlyFinancialTerms ? "1" : "0",
    });
    return `/api/licenses?${sp.toString()}`;
  }, [minConfidence, onlyFinancialTerms, page, search, sortSpec]);

  useEffect(() => {
    const controller = new AbortController();
    async function run() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(requestPath, { signal: controller.signal });
        if (!res.ok) throw new Error(`API ${res.status}`);
        setData((await res.json()) as ApiResponse);
      } catch (err) {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    run();
    return () => controller.abort();
  }, [requestPath]);

  const toggleExpand = (idx: number) => {
    setExpandedIdx(expandedIdx === idx ? null : idx);
  };

  return (
    <div className="min-h-screen bg-[var(--base-bg)] text-[var(--ink)]">
      <div className="mx-auto w-full max-w-[1400px] px-4 py-6 md:px-8">
        <AppNav />

        {/* Header */}
        <section className="rounded-3xl border border-[var(--line)] bg-[linear-gradient(118deg,var(--panel),#eff5ff)] p-6 shadow-[0_16px_36px_rgba(10,32,71,0.08)]">
          <div className="flex items-center gap-3">
            <span className="rounded-lg bg-[var(--accent)] px-2.5 py-1 text-xs font-semibold text-white">LAB</span>
            <h1 className="text-3xl font-bold tracking-tight">SEC Prototype Lab</h1>
          </div>
          <p className="mt-2 text-[var(--muted)]">
            License agreement explorer with inline inspection and quality scoring.
          </p>
        </section>

        {/* KPI Strip */}
        <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-4">
          <KpiChip label="Agreements" value={data?.filtered.agreements} total={data?.overall.agreements} />
          <KpiChip label="Companies" value={data?.filtered.companies} total={data?.overall.companies} />
          <KpiChip label="Both Terms" value={data?.filtered.bothFinancialTerms} total={data?.overall.bothFinancialTerms} />
          <KpiChip label="Avg Royalty" value={data?.filtered.avgRoyaltyRate != null ? `${data.filtered.avgRoyaltyRate.toFixed(2)}%` : "-"} />
        </div>

        {/* Controls */}
        <section className="mt-4 rounded-2xl border border-[var(--line)] bg-[var(--panel)] p-4">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-6">
            <div className="xl:col-span-2">
              <label className="block text-xs font-medium text-[var(--muted)]">Search</label>
              <input
                value={search}
                onChange={(e) => { setPage(1); setSearch(e.target.value); }}
                placeholder="company, licensor, technology..."
                className="mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--accent)]"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-[var(--muted)]">Min Confidence</label>
              <select
                value={minConfidence}
                onChange={(e) => { setPage(1); setMinConfidence(e.target.value); }}
                className="mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-sm outline-none"
              >
                <option value="">Any</option>
                <option value="0.4">0.4+</option>
                <option value="0.6">0.6+</option>
                <option value="0.8">0.8+</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-[var(--muted)]">Sort</label>
              <select
                value={sortOption}
                onChange={(e) => { setPage(1); setSortOption(e.target.value as typeof sortOption); }}
                className="mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-sm outline-none"
              >
                {SORT_OPTIONS.map((o) => <option key={o.key} value={o.key}>{o.label}</option>)}
              </select>
            </div>
            <label className="flex items-end gap-2 text-sm cursor-pointer">
              <input type="checkbox" checked={onlyFinancialTerms} onChange={(e) => { setPage(1); setOnlyFinancialTerms(e.target.checked); }} />
              Financial terms only
            </label>
            <button
              onClick={() => { setSearch(""); setMinConfidence(""); setOnlyFinancialTerms(false); setSortOption("confidence_desc"); setPage(1); }}
              className="h-fit self-end rounded-lg border border-[var(--line)] px-3 py-2 text-sm text-[var(--muted)] transition hover:border-[var(--accent)] hover:text-[var(--accent)]"
            >
              Reset
            </button>
          </div>
        </section>

        {/* Error */}
        {error && (
          <div className="mt-4 rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-700">{error}</div>
        )}

        {/* Card List */}
        <section className="mt-4 space-y-3">
          {loading && <p className="py-8 text-center text-[var(--muted)]">Loading...</p>}

          {!loading && (data?.rows.length || 0) === 0 && (
            <p className="py-8 text-center text-[var(--muted)]">No results for current filters.</p>
          )}

          {!loading && (data?.rows || []).map((row, idx) => {
            const conf = Number(row.confidence) || 0;
            const isOpen = expandedIdx === idx;

            return (
              <article
                key={`${row.cik || row.company || "r"}-${idx}`}
                className={`rounded-xl border bg-white transition-shadow ${
                  isOpen ? "border-[var(--accent)] shadow-lg" : "border-[var(--line)] hover:shadow-md"
                }`}
              >
                {/* Compact Row */}
                <div
                  className="flex cursor-pointer items-center gap-4 px-4 py-3"
                  onClick={() => toggleExpand(idx)}
                >
                  {/* Confidence Badge */}
                  <div className="flex flex-col items-center" style={{ minWidth: 48 }}>
                    <div
                      className="flex h-10 w-10 items-center justify-center rounded-full text-xs font-bold text-white"
                      style={{ backgroundColor: confColor(conf) }}
                    >
                      {(conf * 100).toFixed(0)}
                    </div>
                    <span className="mt-0.5 text-[10px]" style={{ color: confColor(conf) }}>
                      {confLabel(conf)}
                    </span>
                  </div>

                  {/* Main Info */}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold truncate">{row.company || "-"}</span>
                      {row.ticker && <span className="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-xs">{row.ticker}</span>}
                      {row.filing_year && <span className="text-xs text-[var(--muted)]">{row.filing_year}</span>}
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-[var(--muted)]">
                      <span>{row.licensor_name || "?"} &rarr; {row.licensee_name || "?"}</span>
                      {row.tech_category && (
                        <span className="rounded-full bg-[#eef3fb] px-2 py-0.5 text-xs text-[var(--accent)]">
                          {row.tech_category}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Financial Summary */}
                  <div className="hidden md:flex items-center gap-6 text-sm">
                    {row.royalty_rate != null && String(row.royalty_rate).trim() !== "" && (
                      <div className="text-center">
                        <div className="font-mono font-semibold text-[var(--accent)]">{fmtPct(row.royalty_rate)}</div>
                        <div className="text-[10px] text-[var(--muted)]">Royalty</div>
                      </div>
                    )}
                    {row.upfront_amount != null && String(row.upfront_amount).trim() !== "" && (
                      <div className="text-center">
                        <div className="font-mono font-semibold">{fmtMoney(row.upfront_amount, row.upfront_currency)}</div>
                        <div className="text-[10px] text-[var(--muted)]">Upfront</div>
                      </div>
                    )}
                    {row.term_years != null && String(row.term_years).trim() !== "" && (
                      <div className="text-center">
                        <div className="font-mono font-semibold">{row.term_years}y</div>
                        <div className="text-[10px] text-[var(--muted)]">Term</div>
                      </div>
                    )}
                  </div>

                  {/* Expand Indicator */}
                  <span className={`text-[var(--muted)] transition-transform ${isOpen ? "rotate-180" : ""}`}>
                    &#9660;
                  </span>
                </div>

                {/* Expanded Detail */}
                {isOpen && (
                  <div className="border-t border-[var(--line)] px-4 py-4">
                    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                      {/* Parties & Tech */}
                      <div className="space-y-3">
                        <DetailSection title="Parties">
                          <DetailRow label="Licensor" value={row.licensor_name} />
                          <DetailRow label="Licensee" value={row.licensee_name} />
                        </DetailSection>
                        <DetailSection title="Technology">
                          <DetailRow label="Name" value={row.tech_name} />
                          <DetailRow label="Category" value={row.tech_category} />
                          {row.industry && <DetailRow label="Industry" value={row.industry} />}
                        </DetailSection>
                      </div>

                      {/* Financial */}
                      <div className="space-y-3">
                        <DetailSection title="Financial Terms">
                          <DetailRow label="Royalty" value={
                            row.royalty_rate != null && String(row.royalty_rate).trim() !== ""
                              ? `${fmtPct(row.royalty_rate)}${row.royalty_unit && row.royalty_unit !== "%" ? ` (${row.royalty_unit})` : ""}`
                              : null
                          } />
                          <DetailRow label="Upfront" value={
                            row.upfront_amount != null && String(row.upfront_amount).trim() !== ""
                              ? `${row.upfront_currency || "$"}${Number(row.upfront_amount).toLocaleString()}`
                              : null
                          } />
                        </DetailSection>
                        <DetailSection title="Contract">
                          <DetailRow label="Term" value={row.term_years ? `${row.term_years} years` : null} />
                          <DetailRow label="Territory" value={fmtTerritory(row.territory)} />
                        </DetailSection>
                      </div>

                      {/* Reasoning */}
                      <div>
                        <DetailSection title="Extraction Reasoning">
                          <p className="text-sm leading-relaxed text-[var(--muted)]">
                            {row.reasoning || "No reasoning available."}
                          </p>
                        </DetailSection>
                      </div>
                    </div>
                  </div>
                )}
              </article>
            );
          })}
        </section>

        {/* Pagination */}
        <div className="mt-4 flex items-center justify-between rounded-2xl border border-[var(--line)] bg-[var(--panel)] px-4 py-3 text-sm">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={!data || data.pagination.page <= 1}
            className="rounded-lg border border-[var(--line)] px-4 py-1.5 transition hover:bg-gray-50 disabled:opacity-40"
          >
            Prev
          </button>
          <span className="text-[var(--muted)]">
            Page {data?.pagination.page || 1} / {data?.pagination.totalPages || 1}
            <span className="ml-3 font-semibold text-[var(--ink)]">{(data?.pagination.total || 0).toLocaleString()} results</span>
          </span>
          <button
            onClick={() => setPage((p) => Math.min(data?.pagination.totalPages || 1, p + 1))}
            disabled={!data || data.pagination.page >= data.pagination.totalPages}
            className="rounded-lg border border-[var(--line)] px-4 py-1.5 transition hover:bg-gray-50 disabled:opacity-40"
          >
            Next
          </button>
        </div>

        {/* Debug Tools (collapsible) */}
        <section className="mt-4 rounded-2xl border border-dashed border-[var(--line)] bg-[var(--panel)] p-4">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Developer Tools</h3>
          <div className="mt-2 flex gap-2">
            <button
              onClick={() => setShowApiPath(!showApiPath)}
              className={`rounded-lg px-3 py-1.5 text-xs transition ${showApiPath ? "bg-[var(--accent)] text-white" : "border border-[var(--line)] text-[var(--muted)] hover:bg-gray-50"}`}
            >
              API Path
            </button>
            <button
              onClick={() => setShowJsonSample(!showJsonSample)}
              className={`rounded-lg px-3 py-1.5 text-xs transition ${showJsonSample ? "bg-[var(--accent)] text-white" : "border border-[var(--line)] text-[var(--muted)] hover:bg-gray-50"}`}
            >
              Sample JSON
            </button>
          </div>
          {showApiPath && (
            <pre className="mt-2 rounded-lg border border-[var(--line)] bg-white p-3 font-mono text-xs break-all">
              {requestPath}
            </pre>
          )}
          {showJsonSample && (
            <pre className="mt-2 max-h-[300px] overflow-auto rounded-lg border border-[var(--line)] bg-white p-3 font-mono text-xs">
              {JSON.stringify(data?.rows?.[0] || {}, null, 2)}
            </pre>
          )}
        </section>
      </div>
    </div>
  );
}

/* -- Sub-components -- */

function KpiChip({ label, value, total }: { label: string; value?: number | string | null; total?: number | null }) {
  const display = value === null || value === undefined ? "-" : typeof value === "number" ? value.toLocaleString() : value;
  return (
    <div className="flex items-center gap-3 rounded-xl border border-[var(--line)] bg-[var(--panel)] px-4 py-3">
      <div>
        <div className="text-xl font-bold">{display}</div>
        <div className="text-xs text-[var(--muted)]">
          {label}
          {total !== undefined && total !== null && <span className="ml-1 opacity-60">/ {total.toLocaleString()}</span>}
        </div>
      </div>
    </div>
  );
}

function DetailSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-[var(--line)] p-3">
      <h4 className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-[var(--muted)]">{title}</h4>
      <div className="space-y-1.5">{children}</div>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="flex justify-between text-sm">
      <span className="text-[var(--muted)]">{label}</span>
      <span className={`text-right max-w-[200px] ${value && value !== "-" ? "font-medium" : "text-[var(--muted)]"}`}>
        {value || "-"}
      </span>
    </div>
  );
}
