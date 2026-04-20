import fs from "node:fs";
import path from "node:path";

export type SortDir = "asc" | "desc";

export type SortCriterion = {
  key: string;
  dir: SortDir;
};

export type AgreementRecord = {
  company?: string;
  cik?: string;
  ticker?: string;
  licensor_name?: string;
  licensee_name?: string;
  tech_name?: string;
  tech_category?: string;
  filing_type?: string;
  filing_year?: number | string | null;
  confidence?: number | string | null;
  royalty_rate?: number | string | null;
  royalty_unit?: string | null;
  upfront_amount?: number | string | null;
  upfront_currency?: string | null;
  has_upfront?: boolean;
  has_royalty?: boolean;
  territory?: string | null;
  term_years?: number | string | null;
  reasoning?: string | null;
  industry?: string | null;
};

export type SummaryPayload = {
  summary?: {
    scan_timestamp?: string;
    total_license_files?: number;
    scan_errors?: number;
    total_agreements?: number;
    companies_with_licenses?: number;
  };
  financial_completeness?: {
    both?: number;
  };
  all_agreements?: AgreementRecord[];
};

type CacheEntry = {
  mtimeMs: number;
  data: SummaryPayload;
};

type Filters = {
  search: string;
  category: string;
  year: string;
  minConfidence: number | null;
  excludeMissingLicensor: boolean;
  excludeMissingLicensee: boolean;
  excludeMissingRoyalty: boolean;
  excludeMissingUpfront: boolean;
  excludeMissingConfidence: boolean;
};

const NUMERIC_KEYS = new Set([
  "royalty_rate",
  "upfront_amount",
  "filing_year",
  "confidence",
]);

let cache: CacheEntry | null = null;

function resolveDataPath(): string {
  const candidates = [
    process.env.LICENSE_SUMMARY_PATH,
    path.resolve(process.cwd(), "license_summary.json"),
    path.resolve(process.cwd(), "..", "license_summary.json"),
  ].filter(Boolean) as string[];

  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }

  throw new Error(
    `license_summary.json not found. Tried: ${candidates.join(", ")}`,
  );
}

function parseNumber(value: unknown): number | null {
  if (value === null || value === undefined || String(value).trim() === "") {
    return null;
  }
  const n = Number(value);
  return Number.isNaN(n) ? null : n;
}

function hasPresentText(value: unknown): boolean {
  if (value === null || value === undefined) return false;
  const s = String(value).trim().toLowerCase();
  return s !== "" && s !== "-" && s !== "unknown" && s !== "n/a" && s !== "none";
}

function normalizeCategory(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value).trim().toLowerCase();
}

function getComparableValue(row: AgreementRecord, key: string): string | number | null {
  const raw = (row as Record<string, unknown>)[key];
  if (NUMERIC_KEYS.has(key)) return parseNumber(raw);
  if (!hasPresentText(raw)) return null;
  return String(raw).trim().toLowerCase();
}

function isMissingComparable(value: string | number | null): boolean {
  return value === null || value === "";
}

function compareByKey(
  a: AgreementRecord,
  b: AgreementRecord,
  key: string,
  dir: SortDir,
): number {
  const av = getComparableValue(a, key);
  const bv = getComparableValue(b, key);
  const dirMul = dir === "asc" ? 1 : -1;

  const aMissing = isMissingComparable(av);
  const bMissing = isMissingComparable(bv);
  if (aMissing && bMissing) return 0;
  if (aMissing) return 1;
  if (bMissing) return -1;

  if (typeof av === "number" && typeof bv === "number") {
    return (av - bv) * dirMul;
  }

  return (
    String(av).localeCompare(String(bv), undefined, {
      numeric: true,
      sensitivity: "base",
    }) * dirMul
  );
}

export function loadSummaryData(): SummaryPayload {
  const dataPath = resolveDataPath();
  const stat = fs.statSync(dataPath);
  if (cache && cache.mtimeMs === stat.mtimeMs) return cache.data;

  const text = fs.readFileSync(dataPath, "utf-8");
  const data = JSON.parse(text) as SummaryPayload;
  cache = { mtimeMs: stat.mtimeMs, data };
  return data;
}

export function parseSortSpec(spec: string): SortCriterion[] {
  const fallback: SortCriterion[] = [{ key: "confidence", dir: "desc" }];
  if (!spec.trim()) return fallback;

  const out: SortCriterion[] = [];
  for (const token of spec.split(",")) {
    const [rawKey, rawDir] = token.split(":");
    const key = (rawKey || "").trim();
    const dir = (rawDir || "").trim().toLowerCase() === "asc" ? "asc" : "desc";
    if (!key) continue;
    out.push({ key, dir });
  }
  return out.length ? out : fallback;
}

function metrics(rows: AgreementRecord[]) {
  const companySet = new Set(rows.map((r) => r.cik || r.company).filter(Boolean));
  const both = rows.filter((r) => r.has_upfront && r.has_royalty).length;
  const royalties = rows
    .map((r) => parseNumber(r.royalty_rate))
    .filter((n): n is number => n !== null && n > 0 && n < 100);
  const avgRoyalty = royalties.length
    ? Number((royalties.reduce((a, b) => a + b, 0) / royalties.length).toFixed(2))
    : null;

  return {
    agreements: rows.length,
    companies: companySet.size,
    bothFinancialTerms: both,
    avgRoyaltyRate: avgRoyalty,
  };
}

function topCategories(rows: AgreementRecord[], limit = 10) {
  const freq = new Map<string, number>();
  const display = new Map<string, string>();

  rows.forEach((r) => {
    const label = String(r.tech_category || "").trim();
    const key = normalizeCategory(label);
    if (!key) return;
    if (!display.has(key)) display.set(key, label);
    freq.set(key, (freq.get(key) || 0) + 1);
  });

  return [...freq.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([key, value]) => ({
      key,
      label: display.get(key) || key,
      count: value,
    }));
}

function financialBreakdown(rows: AgreementRecord[]) {
  let both = 0;
  let upfrontOnly = 0;
  let royaltyOnly = 0;
  let neither = 0;

  rows.forEach((r) => {
    const hasUpfront = parseNumber(r.upfront_amount) !== null || !!r.has_upfront;
    const hasRoyalty = parseNumber(r.royalty_rate) !== null || !!r.has_royalty;
    if (hasUpfront && hasRoyalty) both += 1;
    else if (hasUpfront) upfrontOnly += 1;
    else if (hasRoyalty) royaltyOnly += 1;
    else neither += 1;
  });

  return [
    { name: "Both", value: both },
    { name: "Upfront Only", value: upfrontOnly },
    { name: "Royalty Only", value: royaltyOnly },
    { name: "Neither", value: neither },
  ];
}

function byFilingYear(rows: AgreementRecord[]) {
  const freq = new Map<string, number>();
  rows.forEach((r) => {
    const y = String(r.filing_year || "").trim();
    if (!y) return;
    freq.set(y, (freq.get(y) || 0) + 1);
  });

  return [...freq.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([year, count]) => ({ year, count }));
}

function categoryOptions(rows: AgreementRecord[]) {
  const freq = new Map<string, number>();
  const display = new Map<string, string>();

  rows.forEach((r) => {
    const label = String(r.tech_category || "").trim();
    const key = normalizeCategory(label);
    if (!key) return;
    if (!display.has(key)) display.set(key, label);
    freq.set(key, (freq.get(key) || 0) + 1);
  });

  const all = [...freq.keys()].sort((a, b) =>
    (display.get(a) || a).localeCompare(display.get(b) || b),
  );
  const top = [...freq.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 30)
    .map(([key]) => key);

  return {
    all: all.map((key) => ({ key, label: display.get(key) || key })),
    top: top.map((key) => ({ key, label: display.get(key) || key })),
  };
}

function matchesFilters(row: AgreementRecord, filters: Filters, topSet: Set<string>) {
  const textPool = [
    row.company,
    row.licensor_name,
    row.licensee_name,
    row.tech_name,
    row.tech_category,
  ]
    .filter(Boolean)
    .map((v) => String(v).toLowerCase());

  const textHit =
    !filters.search ||
    textPool.some((v) => v.includes(filters.search));

  const rowCategory = normalizeCategory(row.tech_category);
  const categoryHit =
    !filters.category ||
    (filters.category === "__others__"
      ? !topSet.has(rowCategory)
      : rowCategory === filters.category);

  const yearHit =
    !filters.year || String(row.filing_year || "") === filters.year;

  const confidenceNum = parseNumber(row.confidence);
  const confidenceHit =
    filters.minConfidence === null ||
    (confidenceNum !== null && confidenceNum >= filters.minConfidence);

  const licensorHit =
    !filters.excludeMissingLicensor || hasPresentText(row.licensor_name);
  const licenseeHit =
    !filters.excludeMissingLicensee || hasPresentText(row.licensee_name);
  const royaltyHit =
    !filters.excludeMissingRoyalty || parseNumber(row.royalty_rate) !== null;
  const upfrontHit =
    !filters.excludeMissingUpfront || parseNumber(row.upfront_amount) !== null;
  const confidenceValueHit =
    !filters.excludeMissingConfidence || confidenceNum !== null;

  return (
    textHit &&
    categoryHit &&
    yearHit &&
    confidenceHit &&
    licensorHit &&
    licenseeHit &&
    royaltyHit &&
    upfrontHit &&
    confidenceValueHit
  );
}

export function queryData(params: {
  page: number;
  pageSize: number;
  filters: Filters;
  sort: SortCriterion[];
}) {
  const payload = loadSummaryData();
  const rows = payload.all_agreements || [];
  const options = categoryOptions(rows);
  const topSet = new Set(options.top.map((c) => c.key));

  const filtered = rows.filter((r) => matchesFilters(r, params.filters, topSet));

  filtered.sort((a, b) => {
    for (const criterion of params.sort) {
      const cmp = compareByKey(a, b, criterion.key, criterion.dir);
      if (cmp !== 0) return cmp;
    }
    return 0;
  });

  const safePageSize = Math.max(1, Math.min(params.pageSize, 200));
  const safePage = Math.max(1, params.page);
  const total = filtered.length;
  const totalPages = Math.max(1, Math.ceil(total / safePageSize));
  const start = (safePage - 1) * safePageSize;
  const pagedRows = filtered.slice(start, start + safePageSize);

  return {
    meta: {
      scanTimestamp: payload.summary?.scan_timestamp || null,
      totalLicenseFiles: payload.summary?.total_license_files || 0,
      scanErrors: payload.summary?.scan_errors || 0,
    },
    overall: metrics(rows),
    filtered: metrics(filtered),
    charts: {
      overall: {
        topCategories: topCategories(rows, 12),
        financialBreakdown: financialBreakdown(rows),
        byYear: byFilingYear(rows),
      },
      filtered: {
        topCategories: topCategories(filtered, 12),
        financialBreakdown: financialBreakdown(filtered),
        byYear: byFilingYear(filtered),
      },
    },
    pagination: {
      page: safePage,
      pageSize: safePageSize,
      total,
      totalPages,
    },
    categories: options,
    rows: pagedRows,
  };
}

export type QueryDataResult = ReturnType<typeof queryData>;
