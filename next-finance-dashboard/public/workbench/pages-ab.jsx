// Variation A: Evidence Ledger — document-centric, editorial, sparse
// Variation B: Comparables Grid — dense pivot table

const { AGREEMENTS, SNAPSHOT, ROYALTY_DIST, FIELDS, RECENT, HEALTH, SAVED_QUERIES } = window.LICENSE_DATA;

/* ══════════════════════════════════════════════════════════════
   VARIATION A · Evidence Ledger
   ══════════════════════════════════════════════════════════════ */

const VarA = () => {
  const [view, setView] = React.useState("all");
  const filtered = AGREEMENTS.filter(a => {
    if (view === "both") return a.sec && a.dart;
    if (view === "sec") return a.sec && !a.dart;
    if (view === "dart") return !a.sec && a.dart;
    return true;
  });

  return (
    <div className="page-inner">
      <header className="page-head">
        <div className="eyebrow">
          <span className="n">VAR · A / EVIDENCE LEDGER</span>
          <span className="rule"/>
          <span className="n">UPDATED {SNAPSHOT.as_of}</span>
        </div>
        <h1>The <em>comparables</em> you read, not the dashboard you skim.</h1>
        <div className="sub">
          Each license agreement is a case file. Open to the clause, jump to the exhibit, pin for comparison.
          <span className="kr">각 라이선스 계약을 문서로 읽는 리서치 워크벤치. 조항 인용, 원문 이동, 비교 핀 고정.</span>
        </div>
      </header>

      <HealthStrip items={HEALTH}/>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 28, marginTop: 28 }}>
        <section>
          <div className="hstack" style={{ justifyContent: "space-between", marginBottom: 12 }}>
            <div className="hstack">
              <span className="upper">Ledger · {filtered.length} entries</span>
              <span className="kr">원장 · 항목 {filtered.length}</span>
            </div>
            <Seg value={view} onChange={setView} options={[
              { value: "all",  label: "All" },
              { value: "both", label: "SEC ∩ DART" },
              { value: "sec",  label: "SEC only" },
              { value: "dart", label: "DART only" },
            ]}/>
          </div>

          {filtered.map(a => (
            <article className="evidence-entry" key={a.id}>
              <div className="meta">
                <div className="date">{a.signed}</div>
                <div>eff. {a.effective}</div>
                <div className="faint" style={{ marginTop: 10 }}>#{a.id}</div>
                <div style={{ marginTop: 10 }}>
                  <Prov sec={a.sec} dart={a.dart}/>
                </div>
                {a.unified_match != null && (
                  <div style={{ marginTop: 8 }}>
                    <span className="chip unified">unified {(a.unified_match * 100).toFixed(0)}%</span>
                  </div>
                )}
              </div>

              <div>
                <h2>
                  {a.licensor} <span className="faint" style={{ fontStyle: "italic", fontWeight: 400 }}>→</span> {a.licensee}
                  <span className="kr">{a.licensor_kr} → {a.licensee_kr}</span>
                </h2>
                <div className="parties">
                  <span className="chip soft">{a.compound}</span>
                  <span style={{ margin: "0 6px" }}>·</span>
                  {a.field}
                  <span style={{ margin: "0 6px" }}>·</span>
                  {a.territory}
                  <span style={{ margin: "0 6px" }}>·</span>
                  {a.exclusive ? "exclusive" : "non-exclusive"}
                </div>

                {a.notable_clause && (
                  <Quote text={a.notable_clause}
                         cite={`Exhibit ${a.sec?.exhibit || "—"} · ${a.licensor} 10-K`}/>
                )}

                <div className="terms">
                  <div>
                    <div className="label">Upfront</div>
                    <div className="val">{fmtUsd(a.upfront_usd_m)}</div>
                  </div>
                  <div>
                    <div className="label">Milestones</div>
                    <div className="val">{fmtUsd(a.milestones_usd_m)}</div>
                  </div>
                  <div>
                    <div className="label">Royalty</div>
                    <div className="val">{fmtRoyalty(a)}{a.royalty_tiered && <span className="kr" style={{ marginLeft: 4 }}>tiered</span>}</div>
                  </div>
                  <div>
                    <div className="label">Term</div>
                    <div className="val">{a.term_years}y</div>
                  </div>
                </div>
              </div>

              <div className="actions">
                <button className="btn sm"><Icon name="pin" size={12}/> Pin for compare</button>
                <button className="btn sm ghost"><Icon name="external" size={12}/> Open exhibit</button>
                <button className="btn sm ghost"><Icon name="scale" size={12}/> Find similar</button>
                <button className="btn sm ghost"><Icon name="download" size={12}/> Export JSON</button>
              </div>
            </article>
          ))}
        </section>

        <aside>
          <Card title="Saved queries" titleKr="저장된 쿼리" n={`${SAVED_QUERIES.length} queries`}>
            <div className="vstack" style={{ gap: 0 }}>
              {SAVED_QUERIES.map(q => (
                <div key={q.id} style={{
                  padding: "10px 0", borderBottom: "1px solid var(--rule-hair)",
                  display: "flex", gap: 8, alignItems: "flex-start",
                }}>
                  <Icon name="bookmark" size={13} style={{ marginTop: 2, color: "var(--ink-muted)" }}/>
                  <div style={{ flex: 1 }}>
                    <div className="t13">{q.name}</div>
                    <div className="kr">{q.kr}</div>
                  </div>
                  <span className="tag-small">{q.n}</span>
                </div>
              ))}
            </div>
          </Card>

          <div style={{ height: 16 }}/>

          <Card title="Recent activity" titleKr="최근 활동">
            <div className="vstack" style={{ gap: 10 }}>
              {RECENT.slice(0, 6).map((r, i) => (
                <div key={i} style={{ display: "grid", gridTemplateColumns: "32px 1fr auto", gap: 8, fontSize: 11.5 }}>
                  <span className="mono faint">{r.t}</span>
                  <span style={{ color: "var(--ink-soft)" }}>{r.msg}</span>
                  <span className={"chip " + r.src}>{r.src}</span>
                </div>
              ))}
            </div>
          </Card>

          <div style={{ height: 16 }}/>

          <Card title="Judge verdict mix" titleKr="판정 분포">
            <div className="vstack" style={{ gap: 8, fontSize: 12 }}>
              <div><span className="upper" style={{ color: "var(--ok)" }}>REAL · 79.3%</span>
                <div className="inline-bar" style={{ marginTop: 4 }}><span style={{ width: "79.3%", background: "var(--ok)" }}/></div>
              </div>
              <div><span className="upper" style={{ color: "var(--warn)" }}>AMBIGUOUS · 14.2%</span>
                <div className="inline-bar" style={{ marginTop: 4 }}><span style={{ width: "14.2%", background: "var(--warn)" }}/></div>
              </div>
              <div><span className="upper" style={{ color: "var(--ink-muted)" }}>FALSE-POS · 6.5%</span>
                <div className="inline-bar" style={{ marginTop: 4 }}><span style={{ width: "6.5%", background: "var(--ink-muted)" }}/></div>
              </div>
            </div>
          </Card>
        </aside>
      </div>
    </div>
  );
};

/* ══════════════════════════════════════════════════════════════
   VARIATION B · Comparables Grid (high-density)
   ══════════════════════════════════════════════════════════════ */

const VarB = () => {
  const [sort, setSort] = React.useState({ key: "signed", dir: "desc" });
  const [pinned, setPinned] = React.useState(new Set(["AGR-04812", "AGR-04751"]));
  const togglePin = (id) => setPinned(prev => {
    const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n;
  });

  const sorted = [...AGREEMENTS].sort((a, b) => {
    const ak = a[sort.key] ?? 0, bk = b[sort.key] ?? 0;
    if (ak < bk) return sort.dir === "asc" ? -1 : 1;
    if (ak > bk) return sort.dir === "asc" ? 1 : -1;
    return 0;
  });

  const H = ({ k, children, right }) => (
    <th className={right ? "r" : ""} onClick={() => setSort(s => ({ key: k, dir: s.key === k && s.dir === "desc" ? "asc" : "desc" }))} style={{ cursor: "pointer" }}>
      {children} {sort.key === k && <span className="mono faint">{sort.dir === "asc" ? "↑" : "↓"}</span>}
    </th>
  );

  const maxUpfront = Math.max(...AGREEMENTS.map(a => a.upfront_usd_m));

  return (
    <div className="page-inner">
      <header className="page-head">
        <div className="eyebrow">
          <span className="n">VAR · B / COMPARABLES GRID</span>
          <span className="rule"/>
          <span className="n">{AGREEMENTS.length} ROWS · SORT BY {sort.key.toUpperCase()}</span>
        </div>
        <h1>All comparables, one <em>surface</em>.</h1>
        <div className="sub">
          Every agreement, every column, every source in one dense grid. Filter, sort, pin, export.
          <span className="kr">모든 비교사례 · 모든 필드 · 모든 출처. 필터 · 정렬 · 핀 · 내보내기.</span>
        </div>
      </header>

      {/* Filter/toolbar row */}
      <div className="card" style={{ padding: 12, marginBottom: 16 }}>
        <div className="hstack" style={{ gap: 10, flexWrap: "wrap" }}>
          <Seg value="all" onChange={() => {}} options={[
            { value: "all",  label: "All sources" },
            { value: "sec",  label: "SEC" },
            { value: "dart", label: "DART" },
            { value: "uni",  label: "Unified" },
          ]}/>
          <div className="chip"><Icon name="filter" size={11}/> Field: Oncology, Autoimmune +3</div>
          <div className="chip"><Icon name="filter" size={11}/> Territory: APAC, Worldwide</div>
          <div className="chip"><Icon name="filter" size={11}/> Royalty ≥ 5%</div>
          <div className="chip"><Icon name="filter" size={11}/> Signed ≥ 2024-01-01</div>
          <span className="spacer"/>
          <span className="faint t11 mono">showing {sorted.length} of {SNAPSHOT.clean_agreements.toLocaleString()}</span>
          <button className="btn sm"><Icon name="download" size={12}/> CSV</button>
          <button className="btn sm"><Icon name="download" size={12}/> JSON</button>
          <button className="btn sm primary"><Icon name="compare" size={12}/> Compare ({pinned.size})</button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 300px", gap: 20 }}>
        <Card pad={false}>
          <table className="ledger">
            <thead>
              <tr>
                <th style={{ width: 24 }}></th>
                <H k="id">ID</H>
                <H k="signed">Signed</H>
                <th>Licensor → Licensee</th>
                <th>Field / Territory</th>
                <H k="upfront_usd_m" right>Upfront</H>
                <H k="milestones_usd_m" right>Milestones</H>
                <H k="royalty_low" right>Royalty</H>
                <H k="term_years" right>Term</H>
                <th className="c">Source</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sorted.map(a => (
                <tr key={a.id} className={pinned.has(a.id) ? "selected" : ""}>
                  <td className="c" onClick={() => togglePin(a.id)} style={{ cursor: "pointer" }}>
                    <Icon name="pin" size={12}
                          style={{ color: pinned.has(a.id) ? "var(--accent)" : "var(--ink-faint)" }}/>
                  </td>
                  <td className="mono t11">{a.id}</td>
                  <td className="mono t12">{a.signed}</td>
                  <td className="licensor">
                    <div>{a.licensor} <span className="faint">→</span> {a.licensee}</div>
                    <div className="kr">{a.licensor_kr} → {a.licensee_kr}</div>
                  </td>
                  <td className="t12">
                    <div>{a.field}</div>
                    <div className="mono faint t11">{a.territory}</div>
                  </td>
                  <td className="r">
                    <div className="hstack" style={{ justifyContent: "flex-end", gap: 8 }}>
                      <div className="inline-bar" style={{ width: 60 }}>
                        <span style={{ width: `${(a.upfront_usd_m / maxUpfront) * 100}%` }}/>
                      </div>
                      <span className="num">{fmtUsd(a.upfront_usd_m)}</span>
                    </div>
                  </td>
                  <td className="r num">{fmtUsd(a.milestones_usd_m)}</td>
                  <td className="r">
                    <span className="num">{fmtRoyalty(a)}</span>
                    {a.royalty_tiered && <span className="chip" style={{ marginLeft: 4, padding: "0 4px" }}>tier</span>}
                  </td>
                  <td className="r num t12">{a.term_years}y</td>
                  <td className="c">
                    <div className="hstack" style={{ justifyContent: "center", gap: 3 }}>
                      {a.sec  && <span className="chip sec"  title={a.sec.accession}>SEC</span>}
                      {a.dart && <span className="chip dart" title={a.dart.rcept_no}>DART</span>}
                      {a.unified_match != null && <span className="chip unified">U</span>}
                    </div>
                  </td>
                  <td>
                    <button className="btn ghost sm"><Icon name="chev" size={12}/></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>

        <aside>
          <Card title="Royalty distribution" titleKr="로열티 분포" n={`n=${SNAPSHOT.royalty_observations}`}>
            <BarHistogram data={ROYALTY_DIST}/>
            <div className="t11 faint mono" style={{ marginTop: 8 }}>median 6.5% · p90 11.2%</div>
          </Card>

          <div style={{ height: 12 }}/>

          <Card title="By field of use" titleKr="분야별" pad={false}>
            <table className="ledger">
              <thead><tr>
                <th>Field</th>
                <th className="r">n</th>
                <th className="r">med. royalty</th>
              </tr></thead>
              <tbody>
                {FIELDS.slice(0, 6).map(f => (
                  <tr key={f.field}>
                    <td className="t12">{f.field}</td>
                    <td className="r num t12">{f.agreements.toLocaleString()}</td>
                    <td className="r num t12">{fmtPct(f.median_royalty)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          <div style={{ height: 12 }}/>

          <Card title={`Compare tray (${pinned.size})`} titleKr="비교 트레이">
            <div className="vstack" style={{ gap: 8 }}>
              {[...pinned].map(id => {
                const a = AGREEMENTS.find(x => x.id === id);
                return (
                  <div key={id} className="evidence-card" style={{ margin: 0 }}>
                    <div className="meta">{id}</div>
                    <div className="title" style={{ fontSize: 12 }}>{a.compound} · {a.licensee}</div>
                    <div className="mono t11 muted" style={{ marginTop: 4 }}>{fmtRoyalty(a)} · {fmtUsd(a.upfront_usd_m)} · {a.term_years}y</div>
                  </div>
                );
              })}
              {pinned.size < 2 && <div className="faint t11">Pin two or more to enable side-by-side view.</div>}
              <button className="btn sm primary" disabled={pinned.size < 2}>Open comparison →</button>
            </div>
          </Card>
        </aside>
      </div>
    </div>
  );
};

Object.assign(window, { VarA, VarB });
