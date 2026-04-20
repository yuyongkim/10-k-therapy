# Design System — License Intelligence Terminal

## Product Context
- **What this is:** A research console for browsing, comparing, and validating SEC and DART license disclosures.
- **Who it's for:** Analysts, legal researchers, and data builders who need to move fast without losing provenance.
- **Space/industry:** Financial data tooling, disclosure analytics, contract intelligence.
- **Project type:** Data-heavy web app and dashboard shell.

## Aesthetic Direction
- **Direction:** Quiet research terminal.
- **Decoration level:** Intentional, not flashy.
- **Mood:** Calm, credible, late-night analyst desk. The interface should feel like a dependable instrument panel, not a startup landing page.
- **Reference stance:** Borrow the discipline of terminal UIs and financial dashboards, but keep the polish modern and readable.

## Typography
- **Display/Hero:** Source Sans 3 semibold, used tightly and sparingly.
- **Body:** Source Sans 3, optimized for long scanning sessions and dense labels.
- **UI/Labels:** Source Sans 3 medium/semibold for tabs, filters, and controls.
- **Data/Tables:** JetBrains Mono for metrics, ticker-like values, and confidence readouts.
- **Code:** JetBrains Mono.
- **Loading:** `next/font/google` with local CSS variables, no extra runtime dependency.
- **Scale:** 11 / 12 / 13 / 16 / 24 / 32 px. Headings stay compact. Numbers can go larger inside KPI cards.

## Color
- **Approach:** Restrained.
- **Primary background:** `#07101d`
- **Surface:** `#0c1828`
- **Elevated surface:** `#152741`
- **Primary text:** `#f4f7fd`
- **Secondary text:** `#c9d7eb`
- **Muted text:** `#98abc8`
- **Accent:** `#7cb3ff`, reserved for active nav, focus states, and key comparisons.
- **Secondary accent:** `#65d7ff`, used in charts and live-status states.
- **CTA / highlight:** `#f2a14a`, reserved for deliberate action, not constant chrome.
- **Success / warning / danger:** `#3dd6a5`, `#f5c86a`, `#ff7c90`
- **Dark mode:** Native default. Saturation stays controlled so long sessions do not glow.

## Spacing
- **Base unit:** 4px.
- **Density:** Comfortable-compact. Dense enough for analysts, not claustrophobic.
- **Scale:** 4 / 8 / 12 / 16 / 20 / 24 / 32 px.

## Layout
- **Approach:** Grid-disciplined shell with editorial restraint.
- **Grid:** Wide desktop canvas up to 1600px, with stacked cards and two-column analytical sections.
- **Max content width:** 1600px.
- **Border radius:** 10px for controls, 14 to 16px for panels and cards.
- **Shell rules:** Strong top nav, soft panels, clear information grouping, and subtle depth instead of bright decoration.

## Motion
- **Approach:** Minimal-functional.
- **Easing:** Short ease-out for entry, ease-in-out for hover and emphasis.
- **Duration:** 150 to 250ms for most interactions.
- **Rule:** Motion should reinforce state changes, not entertain.

## Safe Choices
- Dark analytics shell.
- Monospace numerics.
- Quiet, high-contrast panel surfaces.

## Deliberate Risks
- Use a softer editorial sans instead of generic tech-dashboard typography.
- Keep accent color rare, which makes chart and focus moments feel more credible.
- Add a faint grid and atmospheric lighting in the global shell so the product feels authored, not templated.

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-15 | Established a quiet research-terminal design direction | Fits analyst workflows and supports data density without visual noise |
| 2026-04-15 | Standardized on Source Sans 3 + JetBrains Mono | Better readability than generic dashboard defaults, still implementation-safe |
| 2026-04-15 | Tightened palette to deep navy, ice blue, cyan, and amber | Improves credibility and keeps emphasis meaningful |
