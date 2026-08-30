# Design - Harmoni

A locked design system for Harmoni. Every app-page redesign should read this file
before emitting code. Do not regenerate per page; extend this file only when the
system needs to grow.

## Genre

modern-minimal

## Macrostructure Family

- Marketing pages: Workbench with annotated product captures and concrete HR flows.
- App pages: Workbench with role-aware command panels, signal rows, dense tables and calm action cards.
- Content pages: Long Document with practical sections, legal/payroll notes and compact examples.

## Theme

- `--color-paper`   oklch(100% 0 0)
- `--color-paper-2` oklch(98% 0.010 165)
- `--color-ink`     oklch(21% 0.034 264)
- `--color-ink-2`   oklch(44% 0.037 258)
- `--color-rule`    oklch(91% 0.015 170)
- `--color-accent`  oklch(50% 0.088 181)
- `--color-focus`   oklch(68% 0.112 184)

Accent footprint stays below 5 percent of each app viewport. Teal is the product
anchor; amber, blue and rose are reserved for warnings, operations and risk.

## Typography

- Display: Inter, weight 700, style normal.
- Body: Inter, weight 400.
- Mono: JetBrains Mono, weight 500.
- Display tracking: 0.
- Type scale: compact dashboard scale, not landing-page hero scale.

## Spacing

4-point named scale. Use tokens from `static/css/harmoni-suite.css`:
`--hms-space-2xs`, `--hms-space-xs`, `--hms-space-sm`, `--hms-space-md`,
`--hms-space-lg`, `--hms-space-xl`.

## Motion

- Easings: `--hms-ease-out: cubic-bezier(0.16, 1, 0.3, 1)`.
- Reveal pattern: none for app surfaces; content appears immediately.
- Reduced-motion fallback: remove transforms and transitions.

## Microinteractions Stance

- Silent success. Toasts only for failures or invisible background effects.
- Hover may change background, border or a 1-2 px translation.
- Focus rings appear instantly.
- No bouncy easing, no hover-scale pattern, no `transition: all`.

## CTA Voice

- Primary CTA: filled dark teal, compact, icon plus direct verb.
- Secondary CTA: bordered chip, white surface, icon plus direct verb.

## Per-Page Allowances

- App pages must stay functional and information-dense. No decorative art.
- Public demo pages may use product screenshots and annotated captures.
- Legal/payroll pages favor tables, status rails and evidence trails.

## What Pages Must Share

- Harmoni wordmark and teal placement.
- Inter + JetBrains Mono pairing.
- 8-10 px card radius for app surfaces.
- The same role-aware command vocabulary: RRHH, lideres, colaboradores and direccion.
- Status language that connects data to action: "dato", "senal", "accion", "cierre".

## What Pages May Differ On

- Density by role: HR admin pages can be denser than employee portal pages.
- Accent channel: amber for pending action, rose for risk, blue for operations.
- Layout emphasis: dashboards can prioritize signal boards; portals can prioritize personal next steps.

## Provenance

Locked after studying Mandu Hub's SaaS demo video and current official market
positioning from Buk, Rankmi, Factorial, Runa, Deel and HiBob on 2026-08-30.
The system borrows product patterns, not pixels: unified suite, employee
autoservice, role dashboards, social/recognition signals, climate-to-action,
performance-to-development and payroll/time compliance loops.

## Exports

### tokens.css

```css
:root {
  --color-paper:      oklch(100% 0 0);
  --color-paper-2:    oklch(98% 0.010 165);
  --color-ink:        oklch(21% 0.034 264);
  --color-ink-2:      oklch(44% 0.037 258);
  --color-rule:       oklch(91% 0.015 170);
  --color-accent:     oklch(50% 0.088 181);
  --color-accent-ink: oklch(100% 0 0);
  --color-focus:      oklch(68% 0.112 184);

  --font-display: "Inter", system-ui, sans-serif;
  --font-body:    "Inter", system-ui, sans-serif;
  --font-outlier: "JetBrains Mono", ui-monospace, monospace;

  --space-2xs: 0.5rem; --space-xs: 0.75rem; --space-sm: 1rem;
  --space-md: 1.5rem;  --space-lg: 2rem;    --space-xl: 3rem;

  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --dur-short: 180ms;
  --radius-card: 8px; --radius-panel: 10px; --radius-pill: 999px;
}
```
