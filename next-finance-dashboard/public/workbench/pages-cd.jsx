// Variation C: Split Provenance — mirrored SEC ◁▷ DART with diff seam
// Variation D: Assistant-first — conversation + evidence rail

const { AGREEMENTS: AGR_CD, SNAPSHOT: SNAP_CD, RECENT: RECENT_CD, HEALTH: HEALTH_CD, FIELDS: FIELDS_CD, SAVED_QUERIES: SQ_CD } = window.LICENSE_DATA;

/* ══════════════════════════════════════════════════════════════
   VARIATION C · Split Provenance
   ══════════════════════════════════════════════════════════════ */

const VarC = () => {
  const focus = AGR_CD[0]; // the Helixon / Jeonju agreement

  const SEC_FIELDS = [
    { label: "Licensor",     l: focus.licensor,                         r: focus.licensor_kr,                            mid: "same", kr: "권리자" },
    { label: "Licensee",     l: focus.licensee,                         r: focus.licensee_kr,                            mid: "same", kr: "실시권자" },
    { label: "Compound",     l: focus.compound,                         r: focus.compound,                               mid: "same", kr: "대상 물질" },
    { label: "Field",        l: "Oncology · Solid Tumor",               r: "항암 · 고형암",                                mid: "same", kr: "분야" },
    { label: "Territory",    l: "Asia-Pacific excluding Japan",         r: "아시아태평양 (일본 제외)",                       mid: "same", kr: "영역" },
    { label: "Term",         l: "10 years from First Commercial Sale", r: "최초 상업판매일로부터 10년",                       mid: "same", kr: "기간" },
    { label: "Upfront",      l: "USD 45,000,000",                        r: "USD 45,000,000 (KRW 약 61,500,000,000)",      mid: "same", kr: "선급금" },
    { label: "Milestones",   l: "Up to USD 310M",                        r: "최대 USD 310M",                               mid: "same", kr: "마일스톤" },
    { label: "Royalty",      l: "7%–12% tiered on annual net sales",    r: "연 순매출 기준 7% → 12% 단계",                  mid: "same", kr: "로열티" },
    { label: "Exclusivity",  l: "Exclusive",                             r: "Non-exclusive (영문 계약서 Section 2.1 기준 재확인 필요)", mid: "diff", kr: "배타성" },
    { label: "Effective",    l: "October 1, 2025",                       r: "2025-10-01",                                 mid: "same", kr: "효력 발생" },
    { label: "Signed",       l: "August 14, 2025",                       r: "2025-08-14",                                 mid: "same", kr: "체결일" },
  ];

  return (
    <div className="page-inner">
      <header className="page-head">
        <div className="eyebrow">
          <span className="n">VAR · C / SPLIT PROVENANCE</span>
          <span className="rule"/>
          <span className="n">CASE · {focus.id}</span>
        </div>
        <h1>Mirror the <em>same agreement</em> across two jurisdictions.</h1>
        <div className="sub">
          The unified schema is a reconciliation, not a merge. See SEC 10-K and DART 주요사항보고서 side by side; the seam flags disagreement.
          <span className="kr">SEC 10-K와 DART 공시를 나란히 두고 통합 스키마가 맞춘 필드와 어긋난 필드를 확인합니다.</span>
        </div>
      </header>

      {/* Focused agreement header */}
      <div className="card" style={{ padding: 20, marginBottom: 16 }}>
        <div className="hstack" style={{ gap: 16, flexWrap: "wrap" }}>
          <div>
            <div className="upper">Case file · {focus.id}</div>
            <h2 style={{ fontFamily: "var(--font-serif)", margin: "4px 0 0", fontWeight: 500, fontSize: 22, letterSpacing: "-0.01em" }}>
              {focus.licensor} <span className="faint">→</span> {focus.licensee}
            </h2>
            <div className="kr" style={{ marginTop: 2 }}>{focus.licensor_kr} → {focus.licensee_kr}</div>
          </div>
          <span className="spacer"/>
          <div className="hstack" style={{ gap: 8 }}>
            <span className="chip soft">{focus.compound}</span>
            <span className="chip">{focus.field}</span>
            <span className="chip unified">unified {(focus.unified_match * 100).toFixed(0)}%</span>
            <button className="btn sm"><Icon name="pin" size={12}/> Pin</button>
            <button className="btn sm"><Icon name="scale" size={12}/> Find comparables</button>
          </div>
        </div>
      </div>

      {/* The split */}
      <div className="split-cols" style={{ gridTemplateColumns: "1fr 48px 1fr" }}>
        <div className="col-sec">
          <div className="col-h">
            <span className="dot sec"/>
            SEC 10-K <span className="kr">· 미국 증권거래위원회</span>
            <span className="spacer"/>
            <span className="mono t11 faint">{focus.sec.accession}</span>
          </div>
          <div style={{ padding: 16 }}>
            <div className="t11 upper" style={{ marginBottom: 8 }}>Exhibit {focus.sec.exhibit} · filed {focus.sec.filing_date}</div>
            <Quote text={focus.notable_clause}
                   cite={`${focus.licensor} · Annual Report · Exhibit ${focus.sec.exhibit}`}/>
          </div>
          <div style={{ padding: "0 16px 16px" }}>
            <div className="t11 upper" style={{ marginBottom: 6 }}>Extracted fields (EN source)</div>
            {SEC_FIELDS.map(f => (
              <div key={f.label} style={{ padding: "6px 0", borderBottom: "1px solid var(--rule-hair)", fontSize: 12 }}>
                <div className="upper" style={{ fontSize: 9.5, marginBottom: 2 }}>{f.label}</div>
                <div className="serif">{f.l}</div>
              </div>
            ))}
          </div>
          <div style={{ padding: 16, borderTop: "1px solid var(--rule)", background: "var(--paper-sunken)" }}>
            <button className="btn sm"><Icon name="external" size={12}/> Open on EDGAR</button>
            <button className="btn sm ghost" style={{ marginLeft: 6 }}><Icon name="cite" size={12}/> Quote exhibit</button>
          </div>
        </div>

        <div className="col-seam">
          <div className="seam-mark">↔</div>
          <div className="t11 upper" style={{ writingMode: "vertical-rl", transform: "rotate(180deg)", color: "var(--ink-muted)", letterSpacing: "0.12em" }}>
            UNIFIED SCHEMA · 대조
          </div>
          {SEC_FIELDS.map((f, i) => (
            <div key={i} title={f.label} style={{
              width: 20, height: 20, borderRadius: "50%",
              background: f.mid === "same" ? "var(--ok)" : "var(--warn)",
              opacity: 0.85,
              display: "grid", placeItems: "center",
              color: "var(--paper)",
              fontFamily: "var(--font-mono)", fontSize: 10,
            }}>
              {f.mid === "same" ? "=" : "≠"}
            </div>
          ))}
        </div>

        <div className="col-dart">
          <div className="col-h">
            <span className="dot dart"/>
            DART <span className="kr">· 금융감독원 전자공시</span>
            <span className="spacer"/>
            <span className="mono t11 faint">{focus.dart.rcept_no}</span>
          </div>
          <div style={{ padding: 16 }}>
            <div className="t11 upper" style={{ marginBottom: 8 }}>{focus.dart.report} · filed {focus.dart.filing_date}</div>
            <Quote text="본 계약에 따라 <mark>실시료는 연간 순매출액이 USD 500M 이하일 때 7%, 그 초과분에 대해서는 12%</mark>의 비율로 적용된다. 계약 기간은 각 주요국 최초 상업판매일로부터 10년으로 한다."
                   cite={`${focus.dart.filer} · 주요사항보고서 · 2-(3) 계약의 주요내용`}/>
          </div>
          <div style={{ padding: "0 16px 16px" }}>
            <div className="t11 upper" style={{ marginBottom: 6 }}>추출 필드 (한글 원문)</div>
            {SEC_FIELDS.map(f => (
              <div key={f.label} style={{ padding: "6px 0", borderBottom: "1px solid var(--rule-hair)", fontSize: 12 }}>
                <div className="upper" style={{ fontSize: 9.5, marginBottom: 2, color: f.mid === "diff" ? "var(--warn)" : "var(--ink-faint)" }}>
                  {f.kr} {f.mid === "diff" && "· 불일치"}
                </div>
                <div className="serif">{f.r}</div>
              </div>
            ))}
          </div>
          <div style={{ padding: 16, borderTop: "1px solid var(--rule)", background: "var(--paper-sunken)" }}>
            <button className="btn sm"><Icon name="external" size={12}/> DART 원문 열기</button>
            <button className="btn sm ghost" style={{ marginLeft: 6 }}><Icon name="cite" size={12}/> 조항 인용</button>
          </div>
        </div>
      </div>

      <div style={{ marginTop: 24, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <Card title="Diff ribbon" titleKr="차이 요약" pad={false}>
          {SEC_FIELDS.map((f, i) => (
            <div key={i} className={"diff-row " + (f.mid === "same" ? "match" : "mismatch")}>
              <div className="l" style={{ fontFamily: f.mid === "diff" ? "var(--font-serif)" : "var(--font-mono)", fontSize: 11.5 }}>{f.l}</div>
              <div className="mid">{f.mid === "same" ? "= " + f.label : "≠ " + f.label}</div>
              <div className="r" style={{ fontFamily: f.mid === "diff" ? "var(--font-serif)" : "var(--font-mono)", fontSize: 11.5 }}>{f.r}</div>
            </div>
          ))}
        </Card>

        <Card title="Why the mismatch?" titleKr="불일치 사유">
          <div className="serif" style={{ fontSize: 13.5, lineHeight: 1.65 }}>
            The SEC exhibit classifies this grant as <b>exclusive</b>, but the DART <span className="kr">주요사항보고서</span> lists it as <b>non-exclusive</b>. This is a common artifact of DART's standardized form — the Korean filing treats the per-indication carve-out as a non-exclusive overlay, while the SEC exhibit preserves the original contract language.
          </div>
          <div className="vstack" style={{ gap: 6, marginTop: 14 }}>
            <div className="chip warn">Human review recommended</div>
            <div className="t11 faint mono">LLM-as-Judge confidence: 0.62 · below gate 0.75</div>
          </div>
          <div className="hstack" style={{ gap: 6, marginTop: 14 }}>
            <button className="btn sm primary"><Icon name="flag" size={12}/> Queue for review</button>
            <button className="btn sm"><Icon name="book" size={12}/> Open both sources</button>
          </div>
        </Card>
      </div>
    </div>
  );
};

/* ══════════════════════════════════════════════════════════════
   VARIATION D · Assistant-first
   ══════════════════════════════════════════════════════════════ */

const VarD = () => {
  const messages = [
    { role: "user", text: "Find recent APAC oncology licenses with tiered royalty ≥ 5%, and compare upfront to the industry median." },
    { role: "agent", segments: [
      { text: "Retrieved 7 agreements matching your filters (APAC · Oncology · tiered royalty, low ≥ 5%) from the unified corpus of " },
      { cite: "19,054 clean agreements" },
      { text: ". The most recent is " },
      { cite: "AGR-04812" },
      { text: " — Helixon Therapeutics licensing HLX-229 to Jeonju Biologics at " },
      { cite: "7% → 12% tiered" },
      { text: ", signed 2025-08-14, with USD 45M upfront.\n\nAgainst the oncology comparable set (n=3,814), this upfront sits at the " },
      { cite: "72nd percentile" },
      { text: " — above the median of USD 32M. The royalty structure matches the modal pattern for APAC oncology deals: tiered breakpoint at roughly USD 500M annual net sales." },
    ]},
    { role: "user", text: "Show me the one DART-only entry and flag what the SEC corpus is missing." },
    { role: "agent", segments: [
      { text: "The closest DART-only example in your result set is " },
      { cite: "AGR-04790" },
      { text: " — Nordgate Chemicals licensing NG-CMC-44 to 한울바이오사이언스, filed at " },
      { cite: "rcept_no 20250425000612" },
      { text: " without a corresponding SEC counterpart. The licensor is privately held (no US-listed parent), which is the primary reason it does not surface in EDGAR." },
    ]},
  ];

  return (
    <div className="page-inner">
      <header className="page-head">
        <div className="eyebrow">
          <span className="n">VAR · D / ASSISTANT-FIRST</span>
          <span className="rule"/>
          <span className="n">MODEL · gemini-1.5-pro</span>
        </div>
        <h1>Ask the <em>corpus</em>. Every answer cites its source.</h1>
        <div className="sub">
          A research assistant seated on top of the SEC/DART unified schema. Every claim is a hyperlink; every number is a retrievable evidence card.
          <span className="kr">SEC/DART 통합 스키마 위에서 동작하는 리서치 어시스턴트. 모든 주장은 원문 링크, 모든 수치는 증거 카드에 대응합니다.</span>
        </div>
      </header>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 360px", gap: 20 }}>
        <div className="chat">
          <div className="thread">
            {messages.map((m, i) => (
              m.role === "user"
                ? <div key={i} className="bubble user">{m.text}</div>
                : <div key={i} className="bubble agent">
                    {m.segments.map((s, j) =>
                      s.cite
                        ? <span key={j} className="cite-inline" title="Open evidence">[{s.cite}]</span>
                        : <span key={j}>{s.text}</span>
                    )}
                  </div>
            ))}
            <div className="hstack" style={{ gap: 6, marginTop: 4 }}>
              <button className="btn sm ghost"><Icon name="sparkle" size={12}/> Expand answer</button>
              <button className="btn sm ghost"><Icon name="download" size={12}/> Export to notebook</button>
              <button className="btn sm ghost"><Icon name="scale" size={12}/> Benchmark comparables</button>
            </div>
          </div>
          <div className="composer">
            <textarea placeholder="Ask about royalties, comparables, clauses… · 로열티, 비교사례, 조항에 대해 질문하세요"/>
            <button className="btn primary"><Icon name="chev" size={13}/> Send</button>
          </div>
        </div>

        <aside>
          <div className="upper" style={{ marginBottom: 8 }}>Retrieved evidence · <span className="kr">검색된 증거</span></div>
          {AGR_CD.slice(0, 5).map(a => (
            <div key={a.id} className="evidence-card">
              <div className="hstack" style={{ gap: 4, marginBottom: 4 }}>
                {a.sec && <span className="chip sec">SEC</span>}
                {a.dart && <span className="chip dart">DART</span>}
                {a.unified_match != null && <span className="chip unified">U {(a.unified_match * 100).toFixed(0)}%</span>}
              </div>
              <div className="title">{a.licensor} → {a.licensee}</div>
              <div className="meta">
                {a.id} · {a.compound} · {fmtRoyalty(a)} · {fmtUsd(a.upfront_usd_m)} upfront
              </div>
              {a.notable_clause && (
                <div className="snippet" dangerouslySetInnerHTML={{
                  __html: '"' + a.notable_clause.replace(/<[^>]+>/g, "").slice(0, 110) + '…"'
                }}/>
              )}
              <div className="hstack" style={{ gap: 4, marginTop: 8 }}>
                <button className="btn ghost sm"><Icon name="external" size={11}/> Source</button>
                <button className="btn ghost sm"><Icon name="pin" size={11}/> Pin</button>
              </div>
            </div>
          ))}

          <div className="upper" style={{ margin: "16px 0 8px" }}>Suggested follow-ups · <span className="kr">다음 질문</span></div>
          <div className="vstack" style={{ gap: 6 }}>
            {[
              "Break down by licensee geography",
              "Which of these went to litigation?",
              "Compare to 2020–2022 cohort",
              "Valuation: DCF using median royalty",
            ].map((s, i) => (
              <button key={i} className="btn sm" style={{ justifyContent: "flex-start", width: "100%", background: "var(--paper-sunken)" }}>
                <Icon name="sparkle" size={11}/> {s}
              </button>
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
};

Object.assign(window, { VarC, VarD });
