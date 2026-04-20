import fs from "node:fs";
import path from "node:path";

type RawSection = {
  section_id?: unknown;
  section_mapping?: {
    sec_label?: unknown;
    dart_label?: unknown;
    dart_eng_label?: unknown;
    order_index?: unknown;
  };
  content?: {
    plain_text?: unknown;
    token_count?: unknown;
    has_tables?: unknown;
    has_financial_data?: unknown;
  };
  extracted_insights?: {
    license_costs?: unknown;
    key_business_areas?: unknown;
    competitive_advantages?: unknown;
    regulatory_concerns?: unknown;
    quantitative_profile?: {
      money_mentions_count?: unknown;
      percent_mentions_count?: unknown;
      year_mentions_count?: unknown;
      currency_codes?: unknown;
      money_examples?: unknown;
      percent_examples?: unknown;
      year_examples?: unknown;
    };
    topic_keyword_counts?: {
      business?: unknown;
      advantage?: unknown;
      regulation?: unknown;
    };
  };
};

type RawDocument = {
  document_id?: unknown;
  source_info?: {
    filing_date?: unknown;
    period_end?: unknown;
    document_type?: unknown;
    language?: unknown;
  };
  company?: {
    name?: unknown;
    identifier?: unknown;
    country?: unknown;
  };
  processing_info?: {
    parser_version?: unknown;
    total_tokens?: unknown;
    status?: unknown;
    ingestion_date?: unknown;
  };
  document_intelligence?: {
    total_sections?: unknown;
    sections_with_tables?: unknown;
    risk_keyword_signal?: unknown;
    detected_currencies?: unknown;
  };
  sections?: unknown;
};

export type FilingSummary = {
  fileName: string;
  documentId: string;
  filingDate: string;
  periodEnd: string;
  documentType: string;
  totalTokens: number;
  sectionsTotal: number;
  sectionsWithTables: number;
  sectionsWithFinancial: number;
  riskKeywordSignal: number;
  label: string;
};

export type SectionSummary = {
  sectionKey: string;
  sectionId: string;
  orderIndex: number;
  secLabel: string;
  dartLabel: string;
  dartEngLabel: string;
  tokenCount: number;
  hasTables: boolean;
  hasFinancialData: boolean;
  keywordCounts: {
    business: number;
    advantage: number;
    regulation: number;
  };
  quantitative: {
    moneyMentions: number;
    percentMentions: number;
    yearMentions: number;
    currencies: string[];
  };
  preview: string;
};

export type SectionDetail = SectionSummary & {
  plainText: string;
  keyBusinessAreas: string[];
  competitiveAdvantages: string[];
  regulatoryConcerns: string[];
  moneyExamples: string[];
  percentExamples: string[];
  yearExamples: string[];
  licenseCosts: Record<string, unknown>;
};

export type LicenseKeywordCount = {
  keyword: string;
  count: number;
};

export type LicenseSignalBucket = {
  name: string;
  count: number;
};

export type LicenseCandidate = {
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

export type FilingLicenseAggregate = {
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

type FilingBundle = {
  summary: FilingSummary;
  sourceInfo: {
    filingDate: string;
    periodEnd: string;
    documentType: string;
    language: string;
  };
  processingInfo: {
    parserVersion: string;
    totalTokens: number;
    status: string;
    ingestionDate: string;
  };
  documentIntelligence: {
    totalSections: number;
    sectionsWithTables: number;
    riskKeywordSignal: number;
    detectedCurrencies: Record<string, number>;
  };
  sections: SectionSummary[];
  sectionDetails: Record<string, SectionDetail>;
  licenseCandidates: LicenseCandidate[];
  licenseSummary: FilingLicenseAggregate;
  company: {
    id: string;
    name: string;
    country: string;
  };
};

type CompanyCacheEntry = {
  signature: string;
  company: {
    id: string;
    name: string;
    country: string;
    language: string;
  };
  filings: FilingBundle[];
  basePath: string;
};

export type DartQueryResult = {
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
    sourceInfo: FilingBundle["sourceInfo"];
    processingInfo: FilingBundle["processingInfo"];
    documentIntelligence: FilingBundle["documentIntelligence"];
  };
  trend: {
    tokensByFiling: Array<{ label: string; tokens: number }>;
    riskByFiling: Array<{ label: string; risk: number }>;
    sectionsByFiling: Array<{ label: string; sections: number }>;
  };
  sections: SectionSummary[];
  sectionDetails: Record<string, SectionDetail>;
  licenseCandidates: LicenseCandidate[];
  licenseAggregate: {
    selected: FilingLicenseAggregate;
    byFiling: FilingLicenseAggregate[];
  };
};

const cache = new Map<string, CompanyCacheEntry>();
const LICENSE_KEYWORDS = [
  "license",
  "licensing",
  "royalty",
  "contract",
  "agreement",
  "patent",
  "ip",
  "technology transfer",
  "exclusive",
  "non-exclusive",
] as const;

function asText(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value).trim();
}

function asNumber(value: unknown, fallback = 0): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function asBoolean(value: unknown): boolean {
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value !== 0;
  if (typeof value === "string") {
    const lower = value.trim().toLowerCase();
    return lower === "true" || lower === "1" || lower === "yes";
  }
  return false;
}

function normalizeSpaces(text: string): string {
  return text.replace(/\s+/g, " ").trim();
}

function previewText(text: string, max = 260): string {
  const normalized = normalizeSpaces(text);
  if (normalized.length <= max) return normalized;
  return `${normalized.slice(0, max).trim()}...`;
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => normalizeSpaces(asText(item)))
    .filter((item) => item.length > 0);
}

function asRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

function parseDetectedCurrencies(
  value: unknown,
): Record<string, number> {
  const input = asRecord(value);
  const out: Record<string, number> = {};

  for (const [key, raw] of Object.entries(input)) {
    const amount = asNumber(raw, 0);
    if (amount > 0) out[key] = amount;
  }

  return out;
}

function labelFromSummary(summary: FilingSummary): string {
  if (summary.periodEnd) return summary.periodEnd;
  if (summary.filingDate.length === 8) {
    return `${summary.filingDate.slice(0, 4)}-${summary.filingDate.slice(4, 6)}-${summary.filingDate.slice(6, 8)}`;
  }
  return summary.fileName.replace(".json", "");
}

function resolveBasePath(): string {
  const candidates = [
    process.env.DART_UNIFIED_SCHEMA_PATH,
    path.resolve(process.cwd(), "../data/dart/unified_schema"),
    path.resolve(process.cwd(), "../../data/dart/unified_schema"),
    path.resolve(process.cwd(), "data/dart/unified_schema"),
  ].filter(Boolean) as string[];

  for (const p of candidates) {
    if (!fs.existsSync(p)) continue;
    if (fs.statSync(p).isDirectory()) return p;
  }

  throw new Error(
    `DART unified schema path not found. Tried: ${candidates.join(", ")}`,
  );
}

function resolveCompanyId(basePath: string, requested?: string): string {
  if (requested) {
    const requestedPath = path.join(basePath, requested);
    if (fs.existsSync(requestedPath) && fs.statSync(requestedPath).isDirectory()) {
      return requested;
    }
  }

  const dirs = fs
    .readdirSync(basePath, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort((a, b) => a.localeCompare(b));

  if (!dirs.length) {
    throw new Error(`No company directories found under ${basePath}`);
  }

  return dirs[0];
}

function collectKeywordHits(text: string): string[] {
  const lower = text.toLowerCase();
  return LICENSE_KEYWORDS.filter((keyword) => lower.includes(keyword));
}

function buildLicenseCandidate(
  section: SectionSummary,
  detail: SectionDetail,
): LicenseCandidate {
  const label =
    section.dartEngLabel ||
    section.secLabel ||
    section.dartLabel ||
    section.sectionId;

  const textPool = [
    section.sectionId,
    section.secLabel,
    section.dartLabel,
    section.dartEngLabel,
    section.preview,
    detail.plainText.slice(0, 2000),
  ]
    .join(" ")
    .toLowerCase();

  const keywordHits = collectKeywordHits(textPool);
  const structuredCostKeys = Object.keys(detail.licenseCosts || {}).filter(
    (key) => key.trim().length > 0,
  );

  let score = keywordHits.length * 2;
  if (section.hasFinancialData) score += 1;
  if (section.quantitative.moneyMentions > 0) score += 1;
  if (section.quantitative.percentMentions > 0) score += 1;
  if (structuredCostKeys.length > 0) score += 4;

  return {
    sectionKey: section.sectionKey,
    sectionId: section.sectionId,
    orderIndex: section.orderIndex,
    label,
    score,
    keywordHits,
    structuredCostKeys,
    moneyMentions: section.quantitative.moneyMentions,
    percentMentions: section.quantitative.percentMentions,
    hasFinancialData: section.hasFinancialData,
    preview: section.preview,
  };
}

function toSignalBuckets(candidates: LicenseCandidate[]): LicenseSignalBucket[] {
  const high = candidates.filter((item) => item.score >= 6).length;
  const medium = candidates.filter(
    (item) => item.score >= 3 && item.score <= 5,
  ).length;
  const low = candidates.filter((item) => item.score >= 1 && item.score <= 2).length;
  const none = candidates.filter((item) => item.score === 0).length;

  return [
    { name: "High (6+)", count: high },
    { name: "Medium (3-5)", count: medium },
    { name: "Low (1-2)", count: low },
    { name: "None (0)", count: none },
  ];
}

function topKeywords(candidates: LicenseCandidate[], limit = 8): LicenseKeywordCount[] {
  const frequency = new Map<string, number>();

  candidates.forEach((candidate) => {
    candidate.keywordHits.forEach((keyword) => {
      frequency.set(keyword, (frequency.get(keyword) || 0) + 1);
    });
  });

  return [...frequency.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([keyword, count]) => ({ keyword, count }));
}

function summarizeLicenseCandidates(
  fileName: string,
  label: string,
  candidates: LicenseCandidate[],
): FilingLicenseAggregate {
  const candidateSections = candidates.filter(
    (item) => item.score > 0 || item.structuredCostKeys.length > 0,
  ).length;
  const structuredCostSections = candidates.filter(
    (item) => item.structuredCostKeys.length > 0,
  ).length;
  const highSignalSections = candidates.filter((item) => item.score >= 6).length;
  const totalScore = candidates.reduce((sum, item) => sum + item.score, 0);
  const avgScore = candidates.length
    ? Number((totalScore / candidates.length).toFixed(2))
    : 0;

  return {
    fileName,
    label,
    totalSections: candidates.length,
    candidateSections,
    structuredCostSections,
    highSignalSections,
    avgScore,
    topKeywords: topKeywords(candidates, 8),
    signalBuckets: toSignalBuckets(candidates),
  };
}

function normalizeSection(section: RawSection, index: number): {
  summary: SectionSummary;
  detail: SectionDetail;
} {
  const mapping = section.section_mapping || {};
  const content = section.content || {};
  const insights = section.extracted_insights || {};
  const quantitative = insights.quantitative_profile || {};
  const keywords = insights.topic_keyword_counts || {};

  const sectionId = asText(section.section_id) || `section_${index + 1}`;
  const orderIndex = asNumber(mapping.order_index, index + 1);
  const sectionKey = `${sectionId}__${index + 1}`;
  const plainText = normalizeSpaces(asText(content.plain_text));

  const summary: SectionSummary = {
    sectionKey,
    sectionId,
    orderIndex,
    secLabel: asText(mapping.sec_label),
    dartLabel: asText(mapping.dart_label),
    dartEngLabel: asText(mapping.dart_eng_label),
    tokenCount: asNumber(content.token_count, 0),
    hasTables: asBoolean(content.has_tables),
    hasFinancialData: asBoolean(content.has_financial_data),
    keywordCounts: {
      business: asNumber(keywords.business, 0),
      advantage: asNumber(keywords.advantage, 0),
      regulation: asNumber(keywords.regulation, 0),
    },
    quantitative: {
      moneyMentions: asNumber(quantitative.money_mentions_count, 0),
      percentMentions: asNumber(quantitative.percent_mentions_count, 0),
      yearMentions: asNumber(quantitative.year_mentions_count, 0),
      currencies: asStringArray(quantitative.currency_codes),
    },
    preview: previewText(plainText),
  };

  const detail: SectionDetail = {
    ...summary,
    plainText,
    keyBusinessAreas: asStringArray(insights.key_business_areas),
    competitiveAdvantages: asStringArray(insights.competitive_advantages),
    regulatoryConcerns: asStringArray(insights.regulatory_concerns),
    moneyExamples: asStringArray(quantitative.money_examples),
    percentExamples: asStringArray(quantitative.percent_examples),
    yearExamples: asStringArray(quantitative.year_examples),
    licenseCosts: asRecord(insights.license_costs),
  };

  return { summary, detail };
}

function parseFiling(filePath: string, fileName: string): FilingBundle {
  const raw = JSON.parse(fs.readFileSync(filePath, "utf-8")) as RawDocument;

  const sourceInfo = raw.source_info || {};
  const processingInfo = raw.processing_info || {};
  const documentIntelligence = raw.document_intelligence || {};
  const company = raw.company || {};

  const sectionsRaw = Array.isArray(raw.sections)
    ? (raw.sections as RawSection[])
    : [];

  const sections: SectionSummary[] = [];
  const sectionDetails: Record<string, SectionDetail> = {};

  sectionsRaw.forEach((section, index) => {
    const normalized = normalizeSection(section, index);
    sections.push(normalized.summary);
    sectionDetails[normalized.summary.sectionKey] = normalized.detail;
  });

  const sectionsWithFinancial = sections.filter((section) => section.hasFinancialData).length;
  const sectionsWithTables = sections.filter((section) => section.hasTables).length;

  const summary: FilingSummary = {
    fileName,
    documentId: asText(raw.document_id),
    filingDate: asText(sourceInfo.filing_date),
    periodEnd: asText(sourceInfo.period_end),
    documentType: asText(sourceInfo.document_type),
    totalTokens: asNumber(processingInfo.total_tokens, 0),
    sectionsTotal:
      asNumber(documentIntelligence.total_sections, 0) || sections.length,
    sectionsWithTables:
      asNumber(documentIntelligence.sections_with_tables, 0) || sectionsWithTables,
    sectionsWithFinancial,
    riskKeywordSignal: asNumber(documentIntelligence.risk_keyword_signal, 0),
    label: fileName.replace(".json", ""),
  };

  const filingLabel = labelFromSummary(summary);
  const licenseCandidates = sections
    .map((section) =>
      buildLicenseCandidate(section, sectionDetails[section.sectionKey]),
    )
    .sort((a, b) => a.orderIndex - b.orderIndex);
  const licenseSummary = summarizeLicenseCandidates(
    fileName,
    filingLabel,
    licenseCandidates,
  );

  return {
    summary: {
      ...summary,
      label: filingLabel,
    },
    sourceInfo: {
      filingDate: summary.filingDate,
      periodEnd: summary.periodEnd,
      documentType: summary.documentType,
      language: asText(sourceInfo.language),
    },
    processingInfo: {
      parserVersion: asText(processingInfo.parser_version),
      totalTokens: summary.totalTokens,
      status: asText(processingInfo.status),
      ingestionDate: asText(processingInfo.ingestion_date),
    },
    documentIntelligence: {
      totalSections: summary.sectionsTotal,
      sectionsWithTables: summary.sectionsWithTables,
      riskKeywordSignal: summary.riskKeywordSignal,
      detectedCurrencies: parseDetectedCurrencies(
        documentIntelligence.detected_currencies,
      ),
    },
    sections,
    sectionDetails,
    licenseCandidates,
    licenseSummary,
    company: {
      id: asText(company.identifier),
      name: asText(company.name),
      country: asText(company.country),
    },
  };
}

function loadCompany(basePath: string, companyId: string): CompanyCacheEntry {
  const companyPath = path.join(basePath, companyId);
  if (!fs.existsSync(companyPath) || !fs.statSync(companyPath).isDirectory()) {
    throw new Error(`Company directory not found: ${companyPath}`);
  }

  const files = fs
    .readdirSync(companyPath)
    .filter((name) => name.endsWith(".json"))
    .sort((a, b) => a.localeCompare(b));

  if (!files.length) {
    throw new Error(`No DART json files found under ${companyPath}`);
  }

  const signature = files
    .map((fileName) => {
      const full = path.join(companyPath, fileName);
      return `${fileName}:${fs.statSync(full).mtimeMs}`;
    })
    .join("|");

  const cacheKey = `${companyPath}`;
  const cached = cache.get(cacheKey);
  if (cached && cached.signature === signature) return cached;

  const filings = files.map((fileName) =>
    parseFiling(path.join(companyPath, fileName), fileName),
  );

  const sortedByNewest = [...filings].sort((a, b) =>
    a.summary.fileName.localeCompare(b.summary.fileName),
  );
  const newest = sortedByNewest[sortedByNewest.length - 1];

  const entry: CompanyCacheEntry = {
    signature,
    company: {
      id: newest.company.id || companyId,
      name: newest.company.name || companyId,
      country: newest.company.country || "",
      language: newest.sourceInfo.language || "",
    },
    filings,
    basePath,
  };

  cache.set(cacheKey, entry);
  return entry;
}

export function queryDartData(params: {
  companyId?: string;
  filing?: string;
}): DartQueryResult {
  const basePath = resolveBasePath();
  const companyId = resolveCompanyId(basePath, params.companyId);
  const companyData = loadCompany(basePath, companyId);

  const sortedFilings = [...companyData.filings].sort((a, b) =>
    a.summary.fileName.localeCompare(b.summary.fileName),
  );

  const defaultFiling = sortedFilings[sortedFilings.length - 1];
  const selected = sortedFilings.find(
    (item) => item.summary.fileName === params.filing,
  );
  const selectedFiling = selected || defaultFiling;

  const sectionKeys = selectedFiling.sections
    .map((section) => section.sectionKey)
    .filter((key) => key.length > 0);
  const selectedSectionKey = sectionKeys[0] || "";
  const selectedCandidates = [...selectedFiling.licenseCandidates].sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score;
    return a.orderIndex - b.orderIndex;
  });
  const byFilingAggregate = sortedFilings.map((item) => item.licenseSummary);

  return {
    sourcePath: path.join(companyData.basePath, companyId),
    company: companyData.company,
    filings: sortedFilings.map((item) => item.summary),
    selectedFiling: selectedFiling.summary.fileName,
    selectedSectionKey,
    overview: {
      documentId: selectedFiling.summary.documentId,
      sourceInfo: selectedFiling.sourceInfo,
      processingInfo: selectedFiling.processingInfo,
      documentIntelligence: selectedFiling.documentIntelligence,
    },
    trend: {
      tokensByFiling: sortedFilings.map((item) => ({
        label: item.summary.label,
        tokens: item.summary.totalTokens,
      })),
      riskByFiling: sortedFilings.map((item) => ({
        label: item.summary.label,
        risk: item.summary.riskKeywordSignal,
      })),
      sectionsByFiling: sortedFilings.map((item) => ({
        label: item.summary.label,
        sections: item.summary.sectionsTotal,
      })),
    },
    sections: selectedFiling.sections.sort((a, b) => a.orderIndex - b.orderIndex),
    sectionDetails: selectedFiling.sectionDetails,
    licenseCandidates: selectedCandidates,
    licenseAggregate: {
      selected: selectedFiling.licenseSummary,
      byFiling: byFilingAggregate,
    },
  };
}
