"use client";

import { useEffect, useMemo, useState } from "react";
import { AppNav } from "@/components/app-nav";

type FilingSummary = {
  fileName: string;
  documentType: string;
  filingDate: string;
  totalTokens: number;
  label: string;
};

type SectionSummary = {
  sectionKey: string;
  sectionId: string;
  secLabel: string;
  dartLabel: string;
  dartEngLabel: string;
  tokenCount: number;
  hasTables: boolean;
  hasFinancialData: boolean;
  quantitative: {
    moneyMentions: number;
    percentMentions: number;
    yearMentions: number;
    currencies: string[];
  };
  preview: string;
};

type SectionDetail = SectionSummary & {
  plainText: string;
  licenseCosts: Record<string, unknown>;
};

type LicenseSignalBucket = {
  name: string;
  count: number;
};

type LicenseKeywordCount = {
  keyword: string;
  count: number;
};

type LicenseCandidate = {
  sectionKey: string;
  sectionId: string;
  orderIndex: number;
  label: string;
  score: number;
  keywordHits: string[];
  structuredCostKeys: string[];
  moneyMentions: number;
  percentMentions: number;
  hasFinancialData: boolean;
  preview: string;
};

type FilingLicenseAggregate = {
  fileName: string;
  label: string;
  totalSections: number;
  candidateSections: number;
  structuredCostSections: number;
  highSignalSections: number;
  avgScore: number;
  topKeywords: LicenseKeywordCount[];
  signalBuckets: LicenseSignalBucket[];
};

type DartApiResponse = {
  sourcePath: string;
  company: {
    id: string;
    name: string;
    country: string;
    language: string;
  };
  filings: FilingSummary[];
  selectedFiling: string;
  selectedSectionKey: string;
  overview: {
    documentId: string;
  };
  sections: SectionSummary[];
  sectionDetails: Record<string, SectionDetail>;
  licenseCandidates: LicenseCandidate[];
  licenseAggregate: {
    selected: FilingLicenseAggregate;
    byFiling: FilingLicenseAggregate[];
  };
};

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return value.toLocaleString();
}

function formatDate(yyyymmdd: string): string {
  if (!yyyymmdd || yyyymmdd.length !== 8) return yyyymmdd || "-";
  return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6, 8)}`;
}

function formatRatio(part: number, whole: number): string {
  if (whole <= 0) return "0%";
  return `${((part / whole) * 100).toFixed(1)}%`;
}

function signalBarWidth(part: number, whole: number): string {
  if (whole <= 0) return "0%";
  const pct = Math.max(0, Math.min(100, (part / whole) * 100));
  return `${pct}%`;
}

export default function DartLicensePage() {
  const [data, setData] = useState<DartApiResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [filing, setFiling] = useState("");
  const [minScore, setMinScore] = useState("1");
  const [onlyStructured, setOnlyStructured] = useState(false);
  const [activeSectionKey, setActiveSectionKey] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    async function run() {
      setLoading(true);
      setError(null);

      try {
        const sp = new URLSearchParams();
        if (filing) sp.set("filing", filing);
        const res = await fetch(`/api/dart?${sp.toString()}`, {
          signal: controller.signal,
        });

        if (!res.ok) throw new Error(`API ${res.status}`);
        const payload = (await res.json()) as DartApiResponse;
        setData(payload);

        if (!filing || filing !== payload.selectedFiling) {
          setFiling(payload.selectedFiling);
        }
      } catch (err) {
        if (controller.signal.aborted) return;
        const message = err instanceof Error ? err.message : "Unknown error";
        setError(message);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }

    run();
    return () => controller.abort();
  }, [filing]);

  const candidates = useMemo(() => {
    if (!data) return [];
    const threshold = Number(minScore);
    const validThreshold = Number.isFinite(threshold) ? threshold : 0;

    return data.licenseCandidates
      .filter((item) => item.score >= validThreshold)
      .filter((item) => !onlyStructured || item.structuredCostKeys.length > 0);
  }, [data, minScore, onlyStructured]);

  useEffect(() => {
    if (!candidates.length) {
      setActiveSectionKey("");
      return;
    }

    if (!activeSectionKey || !candidates.some((item) => item.sectionKey === activeSectionKey)) {
      setActiveSectionKey(candidates[0].sectionKey);
    }
  }, [activeSectionKey, candidates]);

  const activeDetail = useMemo(() => {
    if (!data || !activeSectionKey) return null;
    return data.sectionDetails[activeSectionKey] || null;
  }, [activeSectionKey, data]);

  const selectedAggregate = data?.licenseAggregate.selected;
  const rollup = data?.licenseAggregate.byFiling || [];
  const viewStructuredCount = candidates.filter((item) => item.structuredCostKeys.length > 0).length;
  const viewMoneyMentions = candidates.reduce((sum, item) => sum + item.moneyMentions, 0);
  const viewKeywordHits = candidates.reduce((sum, item) => sum + item.keywordHits.length, 0);

  return (
    <div className="min-h-screen bg-[var(--base-bg)] text-[var(--ink)]">
      <div className="mx-auto w-full max-w-[1400px] px-4 py-6 md:px-8">
        <AppNav />

        <section className="rounded-3xl border border-[var(--line)] bg-[linear-gradient(118deg,var(--panel),#eff8f6)] p-6 shadow-[0_16px_36px_rgba(10,32,71,0.08)]">
          <h1 className="text-4xl font-bold tracking-tight">DART License Prototype</h1>
          <p className="mt-2 text-[var(--muted)]">
            Rollup-first view for license signal concentration across DART filings.
          </p>
          <p className="mt-3 font-mono text-xs text-[var(--muted)]">
            Company: {data?.company.name || "-"} ({data?.company.id || "-"}) | Source: {data?.sourcePath || "-"}
          </p>
        </section>

        <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard title="Filings" value={formatNumber(data?.filings.length)} />
          <MetricCard title="Candidates (Filing)" value={formatNumber(selectedAggregate?.candidateSections)} />
          <MetricCard title="Structured (Filing)" value={formatNumber(selectedAggregate?.structuredCostSections)} />
          <MetricCard title="Avg Score (Filing)" value={formatNumber(selectedAggregate?.avgScore)} />
        </div>

        <section className="mt-4 rounded-2xl border border-[var(--line)] bg-[var(--panel)] p-4">
          <h2 className="text-lg font-semibold">Query Controls</h2>
          <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
            <div>
              <label className="block text-sm text-[var(--muted)]">Filing</label>
              <select
                value={filing}
                onChange={(e) => setFiling(e.target.value)}
                className="mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2 outline-none focus:border-[var(--accent)]"
              >
                {(data?.filings || []).map((item) => (
                  <option key={item.fileName} value={item.fileName}>
                    {item.label} | {item.documentType} | {formatDate(item.filingDate)}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm text-[var(--muted)]">Min Candidate Score</label>
              <select
                value={minScore}
                onChange={(e) => setMinScore(e.target.value)}
                className="mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2 outline-none focus:border-[var(--accent)]"
              >
                <option value="0">0+</option>
                <option value="1">1+</option>
                <option value="2">2+</option>
                <option value="4">4+</option>
                <option value="6">6+</option>
              </select>
            </div>

            <label className="flex items-end gap-2 text-sm">
              <input
                type="checkbox"
                checked={onlyStructured}
                onChange={(e) => setOnlyStructured(e.target.checked)}
              />
              Show structured license_costs only
            </label>

            <div className="rounded-lg border border-dashed border-[var(--line)] bg-white px-3 py-2 text-xs text-[var(--muted)]">
              View rows: {formatNumber(candidates.length)} | Structured: {formatNumber(viewStructuredCount)} | Money mentions:{" "}
              {formatNumber(viewMoneyMentions)} | Keyword hits: {formatNumber(viewKeywordHits)}
            </div>
          </div>
        </section>

        {error && (
          <div className="mt-4 rounded-xl border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        )}

        <section className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-[1fr_1fr]">
          <article className="rounded-2xl border border-[var(--line)] bg-[var(--panel)] p-4">
            <h2 className="text-lg font-semibold">License Rollup By Filing</h2>
            <div className="mt-3 overflow-x-auto">
              <table className="min-w-[760px] w-full border-collapse">
                <thead className="bg-[#f5f7fc] text-xs uppercase tracking-wide text-[#4d5870]">
                  <tr>
                    <th className="border-b border-[var(--line)] px-3 py-2 text-left">Filing</th>
                    <th className="border-b border-[var(--line)] px-3 py-2 text-right">Candidates</th>
                    <th className="border-b border-[var(--line)] px-3 py-2 text-right">High</th>
                    <th className="border-b border-[var(--line)] px-3 py-2 text-right">Structured</th>
                    <th className="border-b border-[var(--line)] px-3 py-2 text-right">Avg</th>
                    <th className="border-b border-[var(--line)] px-3 py-2 text-left">Density</th>
                  </tr>
                </thead>
                <tbody>
                  {!rollup.length && (
                    <tr>
                      <td colSpan={6} className="px-3 py-6 text-center text-sm text-[var(--muted)]">
                        No rollup rows.
                      </td>
                    </tr>
                  )}
                  {rollup.map((item) => (
                    <tr key={item.fileName} className="border-b border-[#eef1f7] text-sm">
                      <td className="px-3 py-2">
                        <div className="font-medium">{item.label}</div>
                        <div className="text-xs text-[var(--muted)]">
                          top: {item.topKeywords[0]?.keyword || "-"}
                        </div>
                      </td>
                      <td className="px-3 py-2 text-right">
                        {formatNumber(item.candidateSections)}/{formatNumber(item.totalSections)}
                      </td>
                      <td className="px-3 py-2 text-right">{formatNumber(item.highSignalSections)}</td>
                      <td className="px-3 py-2 text-right">{formatNumber(item.structuredCostSections)}</td>
                      <td className="px-3 py-2 text-right">{formatNumber(item.avgScore)}</td>
                      <td className="px-3 py-2">
                        <div className="h-2.5 w-full rounded-full bg-[#e8edf8]">
                          <div
                            className="h-full rounded-full bg-[#0b4f9c]"
                            style={{
                              width: signalBarWidth(item.candidateSections, item.totalSections),
                            }}
                          />
                        </div>
                        <div className="mt-1 text-xs text-[var(--muted)]">
                          {formatRatio(item.candidateSections, item.totalSections)}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>

          <article className="rounded-2xl border border-[var(--line)] bg-[var(--panel)] p-4">
            <h2 className="text-lg font-semibold">Selected Filing Signal Mix</h2>
            <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
              {(selectedAggregate?.signalBuckets || []).map((bucket) => (
                <div key={bucket.name} className="rounded-lg border border-[var(--line)] bg-white px-3 py-2">
                  <p className="text-xs text-[var(--muted)]">{bucket.name}</p>
                  <p className="text-lg font-semibold">{formatNumber(bucket.count)}</p>
                </div>
              ))}
            </div>

            <h3 className="mt-4 text-sm font-semibold">Top Keywords</h3>
            <ul className="mt-2 space-y-1 text-sm">
              {(selectedAggregate?.topKeywords || []).map((entry) => (
                <li key={entry.keyword} className="flex items-center justify-between rounded bg-white px-2 py-1">
                  <span>{entry.keyword}</span>
                  <span className="font-mono text-xs text-[var(--muted)]">{formatNumber(entry.count)}</span>
                </li>
              ))}
              {!selectedAggregate?.topKeywords?.length && (
                <li className="text-[var(--muted)]">-</li>
              )}
            </ul>
          </article>
        </section>

        <section className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-[1.2fr_0.8fr]">
          <article className="overflow-hidden rounded-2xl border border-[var(--line)] bg-[var(--panel)]">
            <header className="border-b border-[var(--line)] px-4 py-3">
              <h2 className="text-lg font-semibold">Candidate Sections (Selected Filing)</h2>
            </header>
            <div className="overflow-x-auto">
              <table className="min-w-[860px] w-full border-collapse">
                <thead className="bg-[#f5f7fc] text-xs uppercase tracking-wide text-[#4d5870]">
                  <tr>
                    <th className="border-b border-[var(--line)] px-3 py-2 text-left">Section</th>
                    <th className="border-b border-[var(--line)] px-3 py-2 text-left">Label</th>
                    <th className="border-b border-[var(--line)] px-3 py-2 text-right">Score</th>
                    <th className="border-b border-[var(--line)] px-3 py-2 text-right">Money</th>
                    <th className="border-b border-[var(--line)] px-3 py-2 text-left">Signals</th>
                  </tr>
                </thead>
                <tbody>
                  {loading && (
                    <tr>
                      <td colSpan={5} className="px-3 py-6 text-center text-sm text-[var(--muted)]">
                        Loading...
                      </td>
                    </tr>
                  )}
                  {!loading && !error && candidates.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-3 py-6 text-center text-sm text-[var(--muted)]">
                        No candidate sections with the current threshold.
                      </td>
                    </tr>
                  )}
                  {!loading &&
                    !error &&
                    candidates.map((item) => {
                      const selected = item.sectionKey === activeSectionKey;
                      return (
                        <tr
                          key={item.sectionKey}
                          className={`cursor-pointer border-b border-[#eef1f7] text-sm ${
                            selected ? "bg-[#eef5ff]" : "hover:bg-[#f8fbff]"
                          }`}
                          onClick={() => setActiveSectionKey(item.sectionKey)}
                        >
                          <td className="px-3 py-2 font-medium">{item.sectionId}</td>
                          <td className="px-3 py-2">{item.label}</td>
                          <td className="px-3 py-2 text-right">{formatNumber(item.score)}</td>
                          <td className="px-3 py-2 text-right">{formatNumber(item.moneyMentions)}</td>
                          <td className="px-3 py-2">
                            <span className="rounded-md bg-[#e9f1ff] px-2 py-1 text-xs text-[#0b4f9c]">
                              kw {item.keywordHits.length}
                            </span>
                            <span className="ml-2 rounded-md bg-[#eef7ef] px-2 py-1 text-xs text-[#2f6b3c]">
                              {item.structuredCostKeys.length > 0 ? "structured" : "heuristic"}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </div>
          </article>

          <article className="rounded-2xl border border-[var(--line)] bg-[var(--panel)] p-4">
            <h2 className="text-lg font-semibold">Selected Detail</h2>
            {!activeDetail && (
              <p className="mt-3 text-sm text-[var(--muted)]">
                Select a candidate section to inspect its extracted license data.
              </p>
            )}

            {activeDetail && (
              <>
                <p className="mt-2 text-sm">
                  <span className="text-[var(--muted)]">Document</span>
                  <span className="ml-2 font-medium text-[var(--ink)]">{data?.overview.documentId || "-"}</span>
                </p>
                <p className="mt-1 text-sm">
                  <span className="text-[var(--muted)]">Section</span>
                  <span className="ml-2 font-medium text-[var(--ink)]">{activeDetail.sectionId}</span>
                </p>

                <div className="mt-3 rounded-lg border border-[var(--line)] bg-white p-3 text-sm">
                  <p className="font-semibold text-[var(--ink)]">Preview</p>
                  <p className="mt-1 text-[var(--muted)]">{activeDetail.preview || "-"}</p>
                </div>

                <div className="mt-3 rounded-lg border border-[var(--line)] bg-white p-3 text-sm">
                  <p className="font-semibold text-[var(--ink)]">Structured license_costs</p>
                  <pre className="mt-1 max-h-[240px] overflow-auto text-xs">
                    {JSON.stringify(activeDetail.licenseCosts, null, 2)}
                  </pre>
                </div>

                <div className="mt-3 rounded-lg border border-[var(--line)] bg-white p-3 text-sm">
                  <p className="font-semibold text-[var(--ink)]">Text Snippet</p>
                  <p className="mt-1 text-[var(--muted)]">{activeDetail.plainText.slice(0, 800) || "-"}</p>
                </div>
              </>
            )}
          </article>
        </section>
      </div>
    </div>
  );
}

function MetricCard({ title, value }: { title: string; value: string }) {
  return (
    <article className="rounded-2xl border border-[var(--line)] bg-[var(--panel)] p-4 shadow-[0_6px_16px_rgba(10,32,71,0.05)]">
      <h3 className="text-sm text-[var(--muted)]">{title}</h3>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </article>
  );
}
