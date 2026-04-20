"use client";

import { useCallback, useEffect, useState } from "react";
import { AppNav } from "@/components/app-nav";
import { C } from "@/components/theme";
import { ProgressBar, SourceBadge } from "@/components/ui";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

type FinTerm = { type: string; rate: number | null; amount: number | null; unit: string | null; currency: string | null };
type ProgressSnapshot = { annotated: number; target: number };
type ContractData = {
  contract_id: number;
  source_system: string;
  company: string | null;
  filing_year: number | null;
  extraction: {
    licensor: string | null; licensee: string | null; tech_name: string | null;
    tech_category: string | null; territory: string | null;
    exclusivity: string | null; confidence: number | null; model: string | null;
  };
  financial_terms: FinTerm[];
  reasoning: string | null;
  source_text: string;
  progress: ProgressSnapshot;
};
type FieldStats = Record<string, number>;
type Stats = { total: number; target: number; real_license_rate: number; hallucination_rate: number; field_precision: FieldStats; avg_field_accuracy: number };

type VerdictButtonProps = {
  current: boolean | null;
  onChange: (v: boolean) => void;
  labelY: string;
  labelN: string;
};

type FieldRowProps = {
  label: string;
  extracted: string | null;
  correct: boolean | null;
  setCorrect: (v: boolean) => void;
};

function VerdictButton({ current, onChange, labelY, labelN }: VerdictButtonProps) {
  return (
    <div style={{ display: "flex", gap: 4 }}>
      <button
        onClick={() => onChange(true)}
        style={{
          padding: "4px 12px", fontSize: 12, borderRadius: 4, cursor: "pointer", border: "none",
          background: current === true ? C.up : C.bgEl, color: current === true ? "#fff" : C.muted,
          fontWeight: current === true ? 700 : 400, transition: "all 0.15s",
        }}
      >
        {labelY}
      </button>
      <button
        onClick={() => onChange(false)}
        style={{
          padding: "4px 12px", fontSize: 12, borderRadius: 4, cursor: "pointer", border: "none",
          background: current === false ? C.down : C.bgEl, color: current === false ? "#fff" : C.muted,
          fontWeight: current === false ? 700 : 400, transition: "all 0.15s",
        }}
      >
        {labelN}
      </button>
    </div>
  );
}

function FieldRow({ label, extracted, correct, setCorrect }: FieldRowProps) {
  return (
    <div
      style={{
        display: "flex", justifyContent: "space-between", alignItems: "center",
        padding: "8px 0", borderBottom: `1px solid ${C.bd}`,
      }}
    >
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 10, color: C.dim, textTransform: "uppercase", letterSpacing: 0.5 }}>{label}</div>
        <div style={{ fontSize: 14, color: C.text, fontFamily: "var(--font-jetbrains), monospace", marginTop: 2 }}>
          {extracted || <span style={{ color: C.dim }}>--</span>}
        </div>
      </div>
      <VerdictButton current={correct} onChange={setCorrect} labelY="O" labelN="X" />
    </div>
  );
}

function getRoyaltyLabel(financialTerms: FinTerm[]): string | null {
  const royalty = financialTerms.find((term) => term.type === "royalty");
  if (!royalty || royalty.rate == null) return null;
  return `${royalty.rate}${royalty.unit || "%"}`;
}

export default function AnnotatePage() {
  const [item, setItem] = useState<ContractData | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [stats, setStats] = useState<Stats | null>(null);
  const [done, setDone] = useState(false);

  const [licensor, setLicensor] = useState<boolean | null>(null);
  const [licensee, setLicensee] = useState<boolean | null>(null);
  const [techName, setTechName] = useState<boolean | null>(null);
  const [category, setCategory] = useState<boolean | null>(null);
  const [royalty, setRoyalty] = useState<boolean | null>(null);
  const [territory, setTerritory] = useState<boolean | null>(null);
  const [isReal, setIsReal] = useState<boolean | null>(null);
  const [isHallucination, setIsHallucination] = useState<boolean | null>(null);
  const [notes, setNotes] = useState("");

  const resetVerdicts = useCallback(() => {
    setLicensor(null);
    setLicensee(null);
    setTechName(null);
    setCategory(null);
    setRoyalty(null);
    setTerritory(null);
    setIsReal(null);
    setIsHallucination(null);
    setNotes("");
  }, []);

  const loadNext = useCallback(() => {
    setLoading(true);
    resetVerdicts();
    fetch(`${API}/annotation/next`)
      .then((r) => r.json())
      .then((d) => {
        if (d.error) {
          setDone(true);
          setItem(null);
          setLoading(false);
          return;
        }
        setItem(d);
        setDone(false);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [resetVerdicts]);

  useEffect(() => {
    fetch(`${API}/annotation/next`)
      .then((r) => r.json())
      .then((d) => {
        if (d.error) {
          setDone(true);
          setItem(null);
          setLoading(false);
          return;
        }
        setItem(d);
        setLoading(false);
      })
      .catch(() => setLoading(false));

    fetch(`${API}/annotation/stats`).then((r) => r.json()).then(setStats).catch(() => {});
  }, []);

  const allFieldsSet = licensor !== null && licensee !== null && techName !== null
    && category !== null && royalty !== null && territory !== null
    && isReal !== null && isHallucination !== null;

  const submit = useCallback(async () => {
    if (!item || !allFieldsSet) return;
    setSubmitting(true);
    try {
      const res = await fetch(`${API}/annotation/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          contract_id: item.contract_id,
          licensor_correct: licensor,
          licensee_correct: licensee,
          tech_name_correct: techName,
          category_correct: category,
          royalty_correct: royalty,
          territory_correct: territory,
          is_real_license: isReal,
          is_hallucination: isHallucination,
          notes,
        }),
      });
      const data = await res.json();
      if (data.stats) setStats(data.stats);
      loadNext();
    } catch {
      setSubmitting(false);
      return;
    }
    setSubmitting(false);
  }, [allFieldsSet, category, isHallucination, isReal, item, licensor, licensee, loadNext, notes, royalty, techName, territory]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Enter" && allFieldsSet && !submitting) {
        void submit();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [allFieldsSet, submitting, submit]);

  const progress: ProgressSnapshot = item?.progress ?? (stats
    ? { annotated: stats.total, target: stats.target }
    : { annotated: 0, target: 50 });

  return (
    <div className="app-shell">
      <AppNav />
      <div style={{ maxWidth: 960, margin: "0 auto", padding: "28px 24px 48px" }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 8 }}>
          <span className="upper" style={{ fontFamily: "var(--font-jetbrains), monospace", color: C.dim }}>
            ANNOTATION · VALIDATION QUEUE
          </span>
          <span style={{ flex: 1, borderTop: `1px solid ${C.bd}` }} />
        </div>
        <h1 style={{
          fontFamily: "var(--font-serif)",
          fontSize: 28,
          fontWeight: 500,
          letterSpacing: "-0.02em",
          margin: 0,
          lineHeight: 1.1,
        }}>
          Manual <em style={{ fontStyle: "italic", color: C.accent }}>verdicts</em> for paper-quality evaluation
        </h1>
        <p style={{ fontSize: 13, color: C.text2, marginTop: 8, lineHeight: 1.6 }}>
          Review each extracted field, verdict the contract as real/hallucinated, and move on.
          <span style={{ display: "block", color: C.muted, fontSize: 12, marginTop: 2 }}>
            추출된 필드를 검토하고 계약 여부·환각 여부를 판정합니다.
          </span>
        </p>

        <div style={{ marginTop: 16 }}>
          <ProgressBar
            label="Annotation Progress"
            current={progress.annotated}
            total={progress.target || 50}
            color={C.cyan}
            sub={stats ? `Accuracy: ${(stats.avg_field_accuracy * 100).toFixed(1)}% | Hallucination: ${(stats.hallucination_rate * 100).toFixed(1)}%` : undefined}
          />
        </div>

        {done && (
          <div style={{ marginTop: 40, textAlign: "center", color: C.up, fontSize: 20, fontWeight: 700 }}>
            All done. The annotation target is complete.
          </div>
        )}

        {loading && !done && (
          <div style={{ marginTop: 40, textAlign: "center", color: C.dim }}>Loading...</div>
        )}

        {item && !loading && !done && (
          <div style={{ marginTop: 20, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div style={{ background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 10, padding: 18 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <span style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", color: C.muted }}>
                  Extracted Data
                </span>
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  <SourceBadge source={item.source_system} />
                  <span style={{ fontSize: 11, color: C.dim }}>{item.company} {item.filing_year}</span>
                </div>
              </div>

              <FieldRow label="Licensor" extracted={item.extraction.licensor} correct={licensor} setCorrect={setLicensor} />
              <FieldRow label="Licensee" extracted={item.extraction.licensee} correct={licensee} setCorrect={setLicensee} />
              <FieldRow label="Technology" extracted={item.extraction.tech_name} correct={techName} setCorrect={setTechName} />
              <FieldRow label="Category" extracted={item.extraction.tech_category} correct={category} setCorrect={setCategory} />
              <FieldRow label="Royalty" extracted={getRoyaltyLabel(item.financial_terms)} correct={royalty} setCorrect={setRoyalty} />
              <FieldRow label="Territory" extracted={item.extraction.territory} correct={territory} setCorrect={setTerritory} />

              <div style={{ marginTop: 16, padding: "12px 0", borderTop: `2px solid ${C.bd}` }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                  <span style={{ fontSize: 12, color: C.text2 }}>Is this a real license agreement?</span>
                  <VerdictButton current={isReal} onChange={setIsReal} labelY="Yes" labelN="No" />
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: 12, color: C.text2 }}>Is this a hallucination?</span>
                  <VerdictButton current={isHallucination} onChange={setIsHallucination} labelY="Yes" labelN="No" />
                </div>
              </div>

              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Notes (optional)"
                style={{
                  width: "100%", marginTop: 12, padding: 10, background: C.bgInput,
                  border: `1px solid ${C.bd}`, borderRadius: 6, color: C.text,
                  fontSize: 12, resize: "vertical", minHeight: 64, outline: "none",
                }}
              />

              <button
                onClick={() => { void submit(); }}
                disabled={!allFieldsSet || submitting}
                style={{
                  width: "100%", marginTop: 12, padding: "10px 0",
                  background: allFieldsSet ? C.accent : C.bgEl,
                  color: allFieldsSet ? "#fff" : C.dim,
                  border: "none", borderRadius: 6, fontSize: 14, fontWeight: 600,
                  cursor: allFieldsSet ? "pointer" : "not-allowed",
                  transition: "all 0.2s",
                }}
              >
                {submitting ? "Saving..." : "Submit & Next (Enter)"}
              </button>
            </div>

            <div style={{ background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 10, padding: 18 }}>
              <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", color: C.muted, marginBottom: 12 }}>
                Source Evidence
              </div>

              {item.reasoning && (
                <div style={{ marginBottom: 16 }}>
                  <div style={{ fontSize: 10, color: C.dim, textTransform: "uppercase", marginBottom: 4 }}>
                    Model Reasoning
                  </div>
                  <div style={{
                    fontSize: 12, color: C.text2, lineHeight: 1.6,
                    background: C.bgSec, padding: 10, borderRadius: 6,
                    maxHeight: 120, overflow: "auto",
                  }}>
                    {item.reasoning}
                  </div>
                </div>
              )}

              <div>
                <div style={{ fontSize: 10, color: C.dim, textTransform: "uppercase", marginBottom: 4 }}>
                  Original Filing Text
                </div>
                <div style={{
                  fontSize: 12, color: C.text, lineHeight: 1.8,
                  background: C.bgSec, padding: 12, borderRadius: 6,
                  maxHeight: 500, overflow: "auto",
                  fontFamily: "var(--font-inter), sans-serif",
                  whiteSpace: "pre-wrap", wordBreak: "break-word",
                }}>
                  {item.source_text || (
                    <span style={{ color: C.dim }}>
                      Source text not available for this contract.
                      {item.source_system === "EDGAR" && " (SEC filings: check raw HTML in data/raw_filings/)"}
                    </span>
                  )}
                </div>
              </div>

              <div style={{ marginTop: 16, display: "flex", gap: 8, flexWrap: "wrap", fontSize: 11, color: C.dim }}>
                <span style={{ background: C.bgEl, padding: "2px 8px", borderRadius: 4 }}>
                  Model: {item.extraction.model}
                </span>
                <span style={{ background: C.bgEl, padding: "2px 8px", borderRadius: 4 }}>
                  Confidence: {((item.extraction.confidence || 0) * 100).toFixed(0)}%
                </span>
                <span style={{ background: C.bgEl, padding: "2px 8px", borderRadius: 4 }}>
                  ID: {item.contract_id}
                </span>
              </div>
            </div>
          </div>
        )}

        {stats && stats.total > 0 && (
          <div style={{ marginTop: 20, background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 10, padding: 18 }}>
            <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", color: C.muted, marginBottom: 12 }}>
              Running Statistics
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, fontSize: 12 }}>
              <div>
                <div style={{ color: C.dim }}>Annotated</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: C.accent }}>{stats.total}/{stats.target}</div>
              </div>
              <div>
                <div style={{ color: C.dim }}>Avg Accuracy</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: C.up }}>{(stats.avg_field_accuracy * 100).toFixed(1)}%</div>
              </div>
              <div>
                <div style={{ color: C.dim }}>Real License Rate</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: C.cyan }}>{(stats.real_license_rate * 100).toFixed(1)}%</div>
              </div>
              <div>
                <div style={{ color: C.dim }}>Hallucination Rate</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: C.down }}>{(stats.hallucination_rate * 100).toFixed(1)}%</div>
              </div>
            </div>
            <div style={{ marginTop: 12, display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 8 }}>
              {Object.entries(stats.field_precision).map(([field, pct]) => (
                <div key={field} style={{ textAlign: "center" }}>
                  <div style={{ fontSize: 10, color: C.dim, textTransform: "capitalize" }}>{field}</div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: pct >= 0.8 ? C.up : pct >= 0.6 ? C.warn : C.down }}>
                    {(pct * 100).toFixed(0)}%
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
