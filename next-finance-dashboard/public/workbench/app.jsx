// App shell wiring for the SEC/DART License Intelligence workbench.

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accent_hue": 25,
  "density": "default",
  "variation": "A"
}/*EDITMODE-END*/;

const ACCENT_PRESETS = [
  { name: "Oxblood",  kr: "적갈", hue: 25  },
  { name: "Ink",      kr: "먹",  hue: 250 },
  { name: "Moss",     kr: "이끼",hue: 150 },
  { name: "Ochre",    kr: "황토",hue: 75  },
  { name: "Plum",     kr: "자두",hue: 310 },
];

const Tweaks = ({ open, onClose, state, set }) => {
  if (!open) return null;
  return (
    <div className="tweaks">
      <div className="t-head">
        <span className="title">Tweaks <span className="kr">· 디자인 조정</span></span>
        <button className="close" onClick={onClose}><Icon name="close" size={14}/></button>
      </div>
      <div className="t-body">
        <div className="t-row">
          <label>Accent · <span className="kr">강조색</span></label>
          <div className="swatches">
            {ACCENT_PRESETS.map(p => (
              <div key={p.hue}
                   className={"swatch " + (state.accent_hue === p.hue ? "active" : "")}
                   style={{ background: `oklch(45% 0.14 ${p.hue})` }}
                   onClick={() => set("accent_hue", p.hue)}
                   title={p.name + " · " + p.kr}/>
            ))}
          </div>
          <div className="t11 faint">{ACCENT_PRESETS.find(p => p.hue === state.accent_hue)?.name || "Custom"}</div>
        </div>

        <div className="t-row">
          <label>Density · <span className="kr">밀도</span></label>
          <Seg value={state.density} onChange={v => set("density", v)} options={[
            { value: "compact", label: "Compact" },
            { value: "default", label: "Default" },
            { value: "comfy",   label: "Comfy" },
          ]}/>
        </div>

        <div className="t-row">
          <label>Dashboard variation · <span className="kr">대시보드 변형</span></label>
          <Seg value={state.variation} onChange={v => set("variation", v)} options={[
            { value: "A", label: "A · Ledger" },
            { value: "B", label: "B · Grid" },
            { value: "C", label: "C · Split" },
            { value: "D", label: "D · Chat" },
          ]}/>
        </div>

        <div className="t11 faint" style={{ borderTop: "1px solid var(--rule-hair)", paddingTop: 10 }}>
          Keyboard · <span className="mono">1–4</span> cycle variations · <span className="mono">⌘K</span> search
        </div>
      </div>
    </div>
  );
};

function App() {
  const [route, setRoute]     = React.useState("dashboard");
  const [tweaks, setTweaks]   = React.useState(TWEAK_DEFAULTS);
  const [tweaksOpen, setOpen] = React.useState(true);
  const set = (k, v) => setTweaks(t => ({ ...t, [k]: v }));

  // Tweaks host protocol
  React.useEffect(() => {
    const h = (e) => {
      if (e.data?.type === "__activate_edit_mode")   setOpen(true);
      if (e.data?.type === "__deactivate_edit_mode") setOpen(false);
    };
    window.addEventListener("message", h);
    window.parent?.postMessage({ type: "__edit_mode_available" }, "*");
    return () => window.removeEventListener("message", h);
  }, []);

  // Apply tweaks to :root
  React.useEffect(() => {
    const root = document.documentElement;
    root.style.setProperty("--accent-hue", tweaks.accent_hue);
    root.classList.remove("density-compact", "density-comfy");
    if (tweaks.density === "compact") root.classList.add("density-compact");
    if (tweaks.density === "comfy")   root.classList.add("density-comfy");
  }, [tweaks]);

  // Persist route + variation in localStorage (so refresh keeps you in place)
  React.useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem("license-wb-v1") || "{}");
      if (saved.route) setRoute(saved.route);
      if (saved.variation) set("variation", saved.variation);
    } catch {}
  }, []);
  React.useEffect(() => {
    try {
      localStorage.setItem("license-wb-v1", JSON.stringify({ route, variation: tweaks.variation }));
    } catch {}
  }, [route, tweaks.variation]);

  // Keyboard 1-4 to cycle dashboard variations (when on dashboard)
  React.useEffect(() => {
    const h = (e) => {
      if (route !== "dashboard") return;
      if (e.target && /INPUT|TEXTAREA/.test(e.target.tagName)) return;
      if (e.key === "1") set("variation", "A");
      if (e.key === "2") set("variation", "B");
      if (e.key === "3") set("variation", "C");
      if (e.key === "4") set("variation", "D");
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [route]);

  const renderPage = () => {
    if (route === "assistant") return <AssistantRoute/>;
    if (route === "sec")       return <SourceRoute source="sec"/>;
    if (route === "dart")      return <SourceRoute source="dart"/>;
    if (route === "valuation") return <ValuationRoute/>;
    // dashboard
    return (
      <div>
        <div style={{
          position: "sticky", top: 0, zIndex: 5,
          background: "var(--paper)",
          borderBottom: "1px solid var(--rule)",
          padding: "12px 32px",
          display: "flex", alignItems: "center", gap: 16,
        }}>
          <span className="upper">Dashboard · <span className="kr">대시보드</span></span>
          <span className="spacer"/>
          <LayoutPicker value={tweaks.variation} onChange={v => set("variation", v)}/>
        </div>
        {tweaks.variation === "A" && <VarA/>}
        {tweaks.variation === "B" && <VarB/>}
        {tweaks.variation === "C" && <VarC/>}
        {tweaks.variation === "D" && <VarD/>}
      </div>
    );
  };

  return (
    <div className="shell">
      <Topbar route={route} setRoute={setRoute} openTweaks={() => setOpen(true)}/>
      <main className="page">{renderPage()}</main>
      <Tweaks open={tweaksOpen} onClose={() => setOpen(false)} state={tweaks} set={set}/>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App/>);
