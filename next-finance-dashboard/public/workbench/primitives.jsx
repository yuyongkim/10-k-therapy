// Reusable primitives for the Courthouse Archive workbench.

const { useState, useEffect, useMemo, useRef } = React;

/* ── Icon ── minimal glyph set. Line weight 1.5. ── */
const ICONS = {
  search: "M11 19a8 8 0 1 1 5.3-14.0 8 8 0 0 1-5.3 14zM21 21l-4.3-4.3",
  filter: "M4 5h16l-6 8v6l-4-2v-4z",
  pin: "M12 2v10l-3 3h6l-3-3V2M8 14h8M12 17v5",
  bookmark: "M6 3h12v18l-6-4-6 4z",
  book: "M4 5a2 2 0 0 1 2-2h12v18H6a2 2 0 0 0-2 2V5zM6 3v18",
  scale: "M12 3v18M4 6l8-3 8 3M7 10l-3 8h6l-3-8M17 10l-3 8h6l-3-8",
  link: "M10 13a5 5 0 0 0 7.1 0l3-3a5 5 0 1 0-7.1-7.1l-1.1 1.1M14 11a5 5 0 0 0-7.1 0l-3 3a5 5 0 1 0 7.1 7.1l1.1-1.1",
  download: "M12 3v12m-5-5l5 5 5-5M4 21h16",
  plus: "M12 5v14M5 12h14",
  chev: "M9 6l6 6-6 6",
  dot: "M12 12h.01",
  chat: "M4 5h16v11H8l-4 4V5z",
  close: "M6 6l12 12M18 6L6 18",
  flag: "M4 4v17M4 4h12l-2 4 2 4H4",
  compare: "M9 3v18M15 3v18M3 9h18M3 15h18",
  sparkle: "M12 3l2 5 5 2-5 2-2 5-2-5-5-2 5-2z",
  external: "M14 4h6v6M20 4l-9 9M10 4H4v16h16v-6",
  cite: "M8 7v6H4l4 4V7zM20 7v6h-4l4 4V7z",
};

const Icon = ({ name, size = 14, strokeWidth = 1.5, style }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
       stroke="currentColor" strokeWidth={strokeWidth}
       strokeLinecap="round" strokeLinejoin="round" style={style} aria-hidden>
    <path d={ICONS[name] || ICONS.dot}/>
  </svg>
);

/* ── Card ── */
const Card = ({ title, titleKr, n, right, children, pad = true, bodyStyle }) => (
  <section className="card">
    {(title || right) && (
      <header className="card-head">
        {title && (
          <h3>
            {title}
            {titleKr && <span className="kr" style={{ marginLeft: 8 }}>{titleKr}</span>}
          </h3>
        )}
        {n && <span className="n">{n}</span>}
        <span className="spacer"/>
        {right}
      </header>
    )}
    <div className={"card-body" + (pad ? "" : " flush")} style={bodyStyle}>{children}</div>
  </section>
);

/* ── Segmented ── */
const Seg = ({ value, onChange, options }) => (
  <div className="seg">
    {options.map(o => (
      <button key={o.value}
              className={value === o.value ? "active" : ""}
              onClick={() => onChange(o.value)}>{o.label}</button>
    ))}
  </div>
);

/* ── Source chip ── */
const SOURCE_LABELS = { sec: "SEC", dart: "DART", unified: "UNIFIED", lit: "LIT", val: "VAL", uni: "UNIFIED" };
const SourceChip = ({ src, code, form }) => (
  <span className={"chip " + src}>
    <span className={"dot " + src}/>
    <b style={{ fontWeight: 700 }}>{SOURCE_LABELS[src] || src.toUpperCase()}</b>
    {form && <span style={{ opacity: 0.7 }}>· {form}</span>}
    {code && <span>· {code}</span>}
  </span>
);

/* ── Provenance strip ── */
const Prov = ({ sec, dart }) => (
  <div className="prov hstack" style={{ gap: 10, flexWrap: "wrap" }}>
    {sec && (
      <span className="hstack" style={{ gap: 4 }}>
        <SourceChip src="sec" form={sec.form} code={sec.accession}/>
      </span>
    )}
    {dart && (
      <span className="hstack" style={{ gap: 4 }}>
        <SourceChip src="dart" form={dart.report} code={dart.rcept_no}/>
      </span>
    )}
    {!sec && !dart && <span className="faint">— no provenance —</span>}
  </div>
);

/* ── Bilingual label ── */
const BL = ({ en, kr }) => (
  <span>{en} <span className="kr">{kr}</span></span>
);

/* ── Formatters ── */
const fmtUsd = (m) => m == null ? "—" : `$${m.toLocaleString()}M`;
const fmtPct = (x, d = 1) => x == null ? "—" : `${(x * 100).toFixed(d)}%`;
const fmtRoyalty = (a) => {
  if (a.royalty_low == null) return "—";
  if (a.royalty_low === a.royalty_high) return fmtPct(a.royalty_low);
  return `${fmtPct(a.royalty_low)}–${fmtPct(a.royalty_high)}`;
};

/* ── Health strip ── */
const HealthStrip = ({ items }) => (
  <div className="healthstrip">
    {items.map((h, i) => (
      <div className="kpi" key={i}>
        <div className="lbl">{h.label} · <span className="kr">{h.label_kr}</span></div>
        <div className="val">
          {h.value}
          {h.state === "warn" && <small style={{ color: "var(--warn)" }}> · review</small>}
        </div>
        <div className="sub">{h.detail}</div>
      </div>
    ))}
  </div>
);

/* ── Quote (legal passage) ── */
const Quote = ({ text, cite }) => (
  <blockquote className="quote">
    <span dangerouslySetInnerHTML={{ __html: text }}/>
    {cite && <span className="cite">— {cite}</span>}
  </blockquote>
);

/* ── Layout Picker (bottom right) — actually at page top ── */
const LayoutPicker = ({ value, onChange }) => (
  <div className="layout-picker" role="tablist" aria-label="Dashboard variation">
    {[
      { v: "A", k: "1", label: "Evidence Ledger", kr: "증거원장" },
      { v: "B", k: "2", label: "Comparables Grid", kr: "비교표" },
      { v: "C", k: "3", label: "Split Provenance", kr: "이원 대조" },
      { v: "D", k: "4", label: "Assistant-first",  kr: "어시스턴트" },
    ].map(o => (
      <button key={o.v}
              className={"opt " + (value === o.v ? "active" : "")}
              onClick={() => onChange(o.v)}>
        <span className="k">{o.k}</span>
        <span>{o.label}</span>
        <span className="kr">{o.kr}</span>
      </button>
    ))}
  </div>
);

/* ── Topbar ── */
const Topbar = ({ route, setRoute, openTweaks }) => {
  const routes = [
    { id: "dashboard", path: "/",         label: "Dashboard",  kr: "대시보드" },
    { id: "assistant", path: "/assistant",label: "Assistant",  kr: "어시스턴트" },
    { id: "sec",       path: "/sec",      label: "SEC 10-K",   kr: "SEC 10-K" },
    { id: "dart",      path: "/dart",     label: "DART",       kr: "DART" },
    { id: "valuation", path: "/valuation",label: "Valuation",  kr: "가치평가" },
  ];
  return (
    <header className="topbar">
      <div className="brand">
        <div className="mark">§</div>
        <div className="name">
          License Intelligence
          <small>SEC · DART · Comparables Workbench</small>
        </div>
      </div>
      <nav className="routes">
        {routes.map(r => (
          <button key={r.id}
                  className={"route " + (route === r.id ? "active" : "")}
                  onClick={() => setRoute(r.id)}>
            <span className="slash">{r.path}</span>
            <span>{r.label}</span>
            <span className="kr">· {r.kr}</span>
          </button>
        ))}
      </nav>
      <div className="search" role="search">
        <Icon name="search" size={13}/>
        <span>Search agreements, accessions, licensors… <span className="kr">계약 · 공시번호 · 권리자 검색</span></span>
        <kbd>⌘K</kbd>
      </div>
      <div className="right">
        <span className="pill"><span className="dot"/>pipeline · running</span>
        <span className="pill">gemini-1.5-pro</span>
        <button className="btn ghost sm" onClick={openTweaks}>Tweaks</button>
      </div>
    </header>
  );
};

/* ── expose ── */
Object.assign(window, {
  Icon, Card, Seg, SourceChip, Prov, BL,
  fmtUsd, fmtPct, fmtRoyalty,
  HealthStrip, Quote, LayoutPicker, Topbar,
});
