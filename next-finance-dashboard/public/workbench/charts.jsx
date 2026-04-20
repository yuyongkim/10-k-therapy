// Inline SVG charts. No libraries.

const BarHistogram = ({ data, height = 140, accentKey = "count" }) => {
  const max = Math.max(...data.map(d => d[accentKey]));
  const w = 100 / data.length;
  return (
    <div style={{ width: "100%" }}>
      <svg viewBox={`0 0 100 ${height / 2}`} preserveAspectRatio="none"
           style={{ width: "100%", height: height, display: "block" }}>
        {data.map((d, i) => {
          const h = (d[accentKey] / max) * (height / 2 - 12);
          return (
            <g key={i}>
              <rect x={i * w + 0.4} y={height / 2 - h - 10}
                    width={w - 0.8} height={h}
                    fill="var(--accent)" opacity="0.85"/>
            </g>
          );
        })}
      </svg>
      <div style={{ display: "grid", gridTemplateColumns: `repeat(${data.length}, 1fr)`, gap: 0, fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--ink-muted)", marginTop: 4 }}>
        {data.map((d, i) => (
          <div key={i} style={{ textAlign: "center" }}>{d.bucket}</div>
        ))}
      </div>
    </div>
  );
};

const SparkLine = ({ values, height = 36, width = 120 }) => {
  if (!values?.length) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const r = max - min || 1;
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * width;
    const y = height - ((v - min) / r) * (height - 4) - 2;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ width, height, display: "block" }}>
      <polyline points={pts} fill="none" stroke="var(--accent)" strokeWidth="1.5" strokeLinejoin="round"/>
    </svg>
  );
};

/* Cumulative royalty observations per quarter */
const CumulativeArea = ({ height = 160 }) => {
  const quarters = ["22Q1","22Q2","22Q3","22Q4","23Q1","23Q2","23Q3","23Q4","24Q1","24Q2","24Q3","24Q4","25Q1","25Q2","25Q3","25Q4","26Q1"];
  const sec  = [ 40, 85,140,210,290,380,490,610,740,880,1020,1170,1320,1490,1650,1810,1960];
  const dart = [  0,  0, 10, 25, 55, 95,160,240,340,450, 590, 750, 920,1120,1310,1490,1680];
  const both = sec.map((v, i) => v + dart[i]);
  const max = Math.max(...both);
  const w = 800, h = height;
  const toXY = (arr) => arr.map((v, i) => {
    const x = (i / (arr.length - 1)) * w;
    const y = h - (v / max) * (h - 20) - 8;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");

  const areaPath = (arr) => `M0,${h} L${toXY(arr).replace(/ /g, " L")} L${w},${h} Z`;

  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none"
         style={{ width: "100%", height, display: "block" }}>
      {/* grid */}
      {[0.25, 0.5, 0.75].map((p, i) => (
        <line key={i} x1="0" x2={w} y1={h * p} y2={h * p}
              stroke="var(--rule-hair)" strokeWidth="0.5" strokeDasharray="2,2"/>
      ))}
      <path d={areaPath(both)} fill="var(--accent-soft)" opacity="0.7"/>
      <polyline points={toXY(sec)}  fill="none" stroke="var(--sec-tone)"  strokeWidth="1.5"/>
      <polyline points={toXY(dart)} fill="none" stroke="var(--dart-tone)" strokeWidth="1.5"/>
      <polyline points={toXY(both)} fill="none" stroke="var(--accent)"    strokeWidth="2"/>
      {/* x ticks */}
      {quarters.map((q, i) => {
        if (i % 4 !== 0) return null;
        const x = (i / (quarters.length - 1)) * w;
        return (
          <text key={i} x={x} y={h - 2} fontSize="10"
                fontFamily="var(--font-mono)" fill="var(--ink-muted)"
                textAnchor={i === 0 ? "start" : "middle"}>{q}</text>
        );
      })}
    </svg>
  );
};

/* Violin-ish distribution of royalties by field */
const RoyaltyBoxPlot = ({ data, height = 220 }) => {
  const w = 800, h = height;
  const pad = { l: 160, r: 20, t: 10, b: 30 };
  const rowH = (h - pad.t - pad.b) / data.length;
  const maxR = 0.15;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none"
         style={{ width: "100%", height, display: "block" }}>
      {/* x axis grid */}
      {[0.02, 0.05, 0.08, 0.12, 0.15].map((p, i) => {
        const x = pad.l + (p / maxR) * (w - pad.l - pad.r);
        return (
          <g key={i}>
            <line x1={x} x2={x} y1={pad.t} y2={h - pad.b}
                  stroke="var(--rule-hair)" strokeWidth="0.5"/>
            <text x={x} y={h - pad.b + 14} textAnchor="middle"
                  fontSize="10" fontFamily="var(--font-mono)" fill="var(--ink-muted)">{(p * 100).toFixed(0)}%</text>
          </g>
        );
      })}
      {data.map((d, i) => {
        const y = pad.t + i * rowH + rowH / 2;
        // approximate q1/median/q3 around median
        const med = d.median_royalty;
        const q1  = Math.max(0.005, med * 0.7);
        const q3  = Math.min(0.14, med * 1.35);
        const lo  = Math.max(0.005, med * 0.4);
        const hi  = Math.min(0.15, med * 1.8);
        const toX = (v) => pad.l + (v / maxR) * (w - pad.l - pad.r);
        return (
          <g key={d.field}>
            <text x={pad.l - 8} y={y + 3} textAnchor="end"
                  fontSize="11" fontFamily="var(--font-sans)" fill="var(--ink)">{d.field}</text>
            <text x={pad.l - 8} y={y + 15} textAnchor="end"
                  fontSize="10" fontFamily="var(--font-mono)" fill="var(--ink-faint)">n={d.agreements}</text>
            {/* whisker */}
            <line x1={toX(lo)} x2={toX(hi)} y1={y} y2={y}
                  stroke="var(--rule-strong)" strokeWidth="1"/>
            {/* box */}
            <rect x={toX(q1)} y={y - 7} width={toX(q3) - toX(q1)} height={14}
                  fill="var(--accent-soft)" stroke="var(--accent)" strokeWidth="1"/>
            {/* median */}
            <line x1={toX(med)} x2={toX(med)} y1={y - 9} y2={y + 9}
                  stroke="var(--accent-ink)" strokeWidth="2"/>
          </g>
        );
      })}
    </svg>
  );
};

Object.assign(window, { BarHistogram, SparkLine, CumulativeArea, RoyaltyBoxPlot });
