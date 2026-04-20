// Stubs for /assistant /sec /dart /valuation routes.
// Each shows enough scaffolding to show the shell + nav work, not hi-fi finished pages.

const { AGREEMENTS: A2, SNAPSHOT: S2 } = window.LICENSE_DATA;

const StubPage = ({ eyebrow, title, titleEm, sub, subKr, children }) => (
  <div className="page-inner">
    <header className="page-head">
      <div className="eyebrow">
        <span className="n">{eyebrow}</span>
        <span className="rule"/>
        <span className="n">CORPUS · {S2.clean_agreements.toLocaleString()} AGREEMENTS</span>
      </div>
      <h1>{title} <em>{titleEm}</em></h1>
      <div className="sub">{sub}<span className="kr">{subKr}</span></div>
    </header>
    {children}
  </div>
);

const AssistantRoute = () => (
  <StubPage
    eyebrow="/ASSISTANT"
    title="Query workbench."
    titleEm="Strategy-first research."
    sub="Compose multi-step investigations: filter → compare → valuate. Each step is saveable, branchable, and cite-linked to source filings. "
    subKr="다단계 리서치 플로우(필터 → 비교 → 가치평가)를 조합하고, 각 단계별 원문 링크를 유지합니다.">
    <div style={{ display: "grid", gridTemplateColumns: "280px 1fr 300px", gap: 16 }}>
      <Card title="Strategies" titleKr="전략">
        <div className="vstack" style={{ gap: 8 }}>
          {["Comparables sweep","Royalty benchmark","DART-only discovery","Litigation crosswalk","DCF valuation"].map((s, i) => (
            <div key={i} className="evidence-card" style={{ margin: 0 }}>
              <div className="title" style={{ fontSize: 13 }}>{s}</div>
              <div className="mono t11 muted">{["12 steps","8 steps","5 steps","11 steps","14 steps"][i]}</div>
            </div>
          ))}
        </div>
      </Card>

      <Card title="Current investigation" titleKr="진행 중 조사" right={<span className="chip soft">draft</span>}>
        <div className="vstack" style={{ gap: 10 }}>
          {[
            { n: "1", kind: "filter", text: "Oncology · APAC · signed ≥ 2024-01-01", out: "214 agreements" },
            { n: "2", kind: "filter", text: "Royalty low ≥ 5% AND tiered = true", out: "88 agreements" },
            { n: "3", kind: "compare", text: "Group by licensee parent · compute median royalty", out: "21 licensee groups" },
            { n: "4", kind: "query", text: "LLM: summarize tier-break patterns across the 21 groups", out: "≤ USD 500M → 5–8%; > USD 500M → 9–13%" },
            { n: "5", kind: "export", text: "Export to valuation notebook (DCF template)", out: "pending" },
          ].map(s => (
            <div key={s.n} style={{ display: "grid", gridTemplateColumns: "28px 1fr auto", gap: 10, padding: 10, background: "var(--paper-sunken)", borderRadius: 4 }}>
              <div className="mono" style={{ fontSize: 16, color: "var(--accent)" }}>{s.n}</div>
              <div>
                <div className="upper" style={{ fontSize: 9.5 }}>{s.kind}</div>
                <div className="t13">{s.text}</div>
                <div className="mono t11 muted" style={{ marginTop: 3 }}>→ {s.out}</div>
              </div>
              <button className="btn ghost sm"><Icon name="chev" size={12}/></button>
            </div>
          ))}
          <button className="btn" style={{ alignSelf: "flex-start" }}><Icon name="plus" size={12}/> Add step</button>
        </div>
      </Card>

      <Card title="Handoff" titleKr="인계">
        <div className="vstack" style={{ gap: 10, fontSize: 12 }}>
          <div>
            <div className="upper">Produces</div>
            <div className="mono t11 muted">royalty_benchmark.csv</div>
            <div className="mono t11 muted">notebook/dcf_draft.ipynb</div>
          </div>
          <div style={{ borderTop: "1px solid var(--rule-hair)", paddingTop: 10 }}>
            <div className="upper">Source files touched</div>
            <div className="mono t11 muted">214 SEC · 88 DART · 21 unified</div>
          </div>
          <button className="btn sm accent"><Icon name="download" size={12}/> Export bundle</button>
        </div>
      </Card>
    </div>
  </StubPage>
);

const SourceRoute = ({ source }) => {
  const title    = source === "sec" ? "SEC 10-K" : "DART";
  const titleEm  = source === "sec" ? "License exhibits, footnotes, extractions." : "주요사항보고서 · 기술도입계약서 드릴다운";
  const sub      = source === "sec"
    ? "Every SEC filing whose exhibits or footnotes mention royalties, licensing, or tech-transfer. Drill to filer, exhibit, clause."
    : "DART 공시 중 라이선스 · 기술도입 · 로열티 관련 항목. 공시자별, 보고서별, 조항별 드릴다운.";
  const subKr    = source === "sec"
    ? "로열티, 라이선싱, 기술이전이 언급된 SEC 공시 · 제출자 · 첨부자료 · 조항 기준 드릴다운."
    : "";
  const filtered = AGREEMENTS.filter(a => source === "sec" ? a.sec : a.dart);
  const chipClass = source === "sec" ? "sec" : "dart";

  return (
    <StubPage
      eyebrow={"/" + source.toUpperCase() + " · " + (source === "sec" ? "EDGAR" : "금융감독원")}
      title={title}
      titleEm={titleEm}
      sub={sub}
      subKr={subKr}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 20 }}>
        <Card pad={false}>
          <div style={{ padding: 12, borderBottom: "1px solid var(--rule)", display: "flex", gap: 8, alignItems: "center" }}>
            <span className={"chip " + chipClass}>{source.toUpperCase()}</span>
            <span className="upper">{filtered.length} filings with extracted license terms</span>
            <span className="spacer"/>
            <button className="btn sm"><Icon name="download" size={12}/> Export</button>
          </div>
          <table className="ledger">
            <thead><tr>
              <th>{source === "sec" ? "Accession" : "Rcept no."}</th>
              <th>Filer</th>
              <th>{source === "sec" ? "Exhibit" : "Report"}</th>
              <th>Filing date</th>
              <th>Agreement</th>
              <th className="r">Royalty</th>
              <th></th>
            </tr></thead>
            <tbody>
              {filtered.map(a => {
                const p = source === "sec" ? a.sec : a.dart;
                return (
                  <tr key={a.id}>
                    <td className="mono t11">{source === "sec" ? p.accession : p.rcept_no}</td>
                    <td className="t12">{source === "sec" ? `CIK ${p.filer_cik}` : p.filer}</td>
                    <td className="t12">{source === "sec" ? `Ex. ${p.exhibit}` : p.report}</td>
                    <td className="mono t12">{p.filing_date}</td>
                    <td className="t12">{a.licensor} → {a.licensee}</td>
                    <td className="r num t12">{fmtRoyalty(a)}</td>
                    <td><button className="btn ghost sm"><Icon name="external" size={11}/></button></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Card>

        <aside>
          <Card title="Filers" titleKr="공시자" pad={false}>
            <table className="ledger">
              <tbody>
                {[...new Set(filtered.map(a => source === "sec" ? a.licensor : a.licensee))].map(f => (
                  <tr key={f}>
                    <td className="t12">{f}</td>
                    <td className="r num t12">{filtered.filter(a => (source === "sec" ? a.licensor : a.licensee) === f).length}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
          <div style={{ height: 12 }}/>
          <Card title="Evidence jump" titleKr="원문 이동">
            <div className="t12 muted">
              Click any {source === "sec" ? "accession" : "rcept_no"} chip to open the original filing in a new tab.
              <span className="kr" style={{ display: "block", marginTop: 4 }}>
                {source === "sec" ? "accession" : "rcept_no"} 클릭 시 원문 공시 페이지로 이동합니다.
              </span>
            </div>
          </Card>
        </aside>
      </div>
    </StubPage>
  );
};

const ValuationRoute = () => (
  <StubPage
    eyebrow="/VALUATION"
    title="DCF with"
    titleEm="comparable-anchored assumptions."
    sub="Every royalty, milestone, and territory assumption links back to the comparables that justify it. No hidden inputs."
    subKr="할인현금흐름의 모든 입력값(로열티 · 마일스톤 · 영역)은 근거가 되는 비교사례에 직접 링크됩니다.">
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
      <Card title="Assumptions · HLX-229 · APAC ex-Japan" titleKr="가정값">
        <table className="ledger">
          <tbody>
            {[
              ["Peak sales", "USD 1,200M", "APAC oncology n=3,814 · p75"],
              ["Royalty (≤500M)", "7.0%", "median comparables (n=42) · 7.0%"],
              ["Royalty (>500M)", "12.0%", "tier-break pattern · 9 of 11 deals"],
              ["Upfront", "USD 45M", "p72 of APAC oncology cohort"],
              ["Milestones", "USD 310M", "median USD 280M · σ 110M"],
              ["POS at Ph2", "35%", "oncology industry benchmark"],
              ["Discount rate", "11.5%", "biotech cost-of-equity (n=184)"],
            ].map((r, i) => (
              <tr key={i}>
                <td className="t12">{r[0]}</td>
                <td className="r num t12">{r[1]}</td>
                <td className="t11 muted">{r[2]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <Card title="Output" titleKr="산출">
        <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 0, border: "1px solid var(--rule)" }}>
          {[
            ["rNPV", "USD 186M", "post risk-adjusted"],
            ["NPV (unrisked)", "USD 531M", "peak-sales scenario"],
            ["Payback", "6.8 yrs", "from first commercial sale"],
            ["Royalty-adj.", "USD 92M", "licensor's share"],
          ].map((r, i) => (
            <div className="kpi" key={i} style={{ borderBottom: i < 2 ? "1px solid var(--rule)" : 0 }}>
              <div className="lbl">{r[0]}</div>
              <div className="val">{r[1]}</div>
              <div className="sub">{r[2]}</div>
            </div>
          ))}
        </div>
        <div className="t11 muted" style={{ marginTop: 12 }}>
          Sensitivity: ±1% on royalty high-tier moves rNPV by USD ±14M · peak sales ±USD 200M moves rNPV USD ±31M.
        </div>
      </Card>
    </div>
  </StubPage>
);

Object.assign(window, { AssistantRoute, SourceRoute, ValuationRoute });
