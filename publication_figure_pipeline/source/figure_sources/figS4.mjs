// Supplementary Figure S4 — Uncertainty and evidence robustness.
// Panel a: forest plot of seed-cluster bootstrap 95% CIs for FAIL-class macro-F1
// differences. Panel b: evidence-traceability endpoints (same encoding as Figure 2b).
// Panel c: recoverability by returned-snippet count (aggregate means across systems;
// undefined values are omitted, never plotted as zero).
// Data: ../data_json_or_csv/figS4.json (canonical, audit-locked). No numbers here.

import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Svg, scaleLinear, f3, textWidth } from './svgkit.mjs';
import { COLORS, SIZE, METRIC_STYLE, STROKE, PT, isRegex } from './style.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const data = JSON.parse(readFileSync(join(here, '../data_json_or_csv/figS4.json'), 'utf8'));

const W = 170, H = 136;
const svg = new Svg(W, H);

// ---------------------------------------------------------------- panel a (forest)
const rowsA = data.panels.a.rows;
const A = { labelX: 43, x0: 45.5, x1: 166, gridTop: 14.5, rowY0: 16.6, rowH: 4.4, gap: 1.3, axisY: 58.2 };
const aRowY = (i) => A.rowY0 + A.rowH * i + (i > 2 ? A.gap : 0) + (i > 5 ? A.gap : 0);
const scaleA = scaleLinear(-0.04, 0.26, A.x0, A.x1); // covers [min ci_lo, max ci_hi] with padding
const A_TICKS = [0, 0.05, 0.10, 0.15, 0.20, 0.25];

svg.panelLetter(4, 7.2, 'a');
svg.panelTitle(8.2, 7.2, data.panels.a.title);

// background: gridlines (non-zero ticks), scope-tier separators, dashed zero reference
for (const t of A_TICKS.filter((t) => t !== 0)) {
  svg.line(scaleA(t), A.gridTop, scaleA(t), A.axisY, { stroke: COLORS.grid, sw: STROKE.grid, cls: 'grid' });
}
for (const brk of [2, 5]) {
  const y = (aRowY(brk) + aRowY(brk + 1)) / 2;
  svg.line(A.x0, y, A.x1, y, { stroke: COLORS.midGrey, sw: 0.5 * PT, dash: '1.6,1.3', cls: 'group-separator' });
}
svg.line(scaleA(0), A.gridTop, scaleA(0), A.axisY,
  { stroke: COLORS.subtext, sw: 0.75 * PT, dash: '2,1.4', cls: 'zero-reference' });

// row labels + CI whiskers with end caps + point estimates
rowsA.forEach((r, i) => {
  const y = aRowY(i);
  svg.text(A.labelX, y + SIZE.label * 0.35, r.label, { size: SIZE.label, anchor: 'end', cls: 'row-label' });
  const xLo = scaleA(r.ci_lo), xHi = scaleA(r.ci_hi);
  svg.line(xLo, y, xHi, y, { stroke: COLORS.darkGrey, sw: STROKE.errorbar, cls: 'ci-whisker' });
  svg.line(xLo, y - 0.9, xLo, y + 0.9, { stroke: COLORS.darkGrey, sw: STROKE.errorbar, cls: 'ci-cap' });
  svg.line(xHi, y - 0.9, xHi, y + 0.9, { stroke: COLORS.darkGrey, sw: STROKE.errorbar, cls: 'ci-cap' });
  svg.marker(scaleA(r.delta), y, 'circle', 1.4, COLORS.blue, { cls: 'marker point-estimate' });
});
svg.xAxis(A.x0, A.x1, A.axisY, A_TICKS, scaleA,
  { title: 'Difference in FAIL-class macro-F1 (95% cluster-bootstrap CI)', fmtDp: 2, titleDy: 5.0 });

// -------------------------------------------------- panels b + c shared header row
const BC_LETTER_Y = 71.6;
svg.panelLetter(4, BC_LETTER_Y, 'b');
svg.panelTitle(8.2, BC_LETTER_Y, data.panels.b.title);
svg.panelLetter(82, BC_LETTER_Y, 'c');
svg.panelTitle(86.2, BC_LETTER_Y, data.panels.c.title);

// ------------------------------------------------------ panel b (evidence endpoints)
const serB = data.panels.b.series;
const nB = serB.length; // 11
const B = { labelX: 21.5, x0: 23.5, x1: 76.5, gridTop: 80.7, rowY0: 82.5, rowH: 4.0, regexGap: 1.5, axisY: 127.5 };
const bRowY = (i) => B.rowY0 + B.rowH * i + (i === nB - 1 ? B.regexGap : 0);
const scaleB = scaleLinear(0.55, 1.01, B.x0, B.x1);

// compact legend above the panel (two rows, inside panel b's column)
let lx = 4;
lx = svg.legendItem(lx, 75.0, METRIC_STYLE.coverage);
lx = svg.legendItem(lx, 75.0, METRIC_STYLE.conditional);
svg.legendItem(4, 78.2, METRIC_STYLE.allSnippet);

for (let i = 0; i < nB; i++) {
  svg.line(B.x0, bRowY(i), B.x1, bRowY(i), { stroke: '#EDF0F4', sw: 0.45 * PT, cls: 'row-guide' });
}
const sepY = (bRowY(nB - 2) + bRowY(nB - 1)) / 2;
svg.line(B.x0, sepY, B.x1, sepY, { stroke: COLORS.midGrey, sw: 0.6 * PT, dash: '2,1.4', cls: 'regex-separator' });

serB.forEach((s, i) => {
  svg.text(B.labelX, bRowY(i) + SIZE.label * 0.35, s.model, { size: SIZE.label, anchor: 'end', cls: 'row-label' });
});
// marker radii per metric (conditional diamond runs smaller: its 1.25x vertical
// stretch would otherwise touch adjacent rows' markers at this row pitch)
const ENDPOINTS = [
  ['evidence_coverage', METRIC_STYLE.coverage, -1.5, 1.15],
  ['conditional_item_recoverability', METRIC_STYLE.conditional, 0, 1.0],
  ['all_snippet_recoverability', METRIC_STYLE.allSnippet, 1.5, 1.15],
];
serB.forEach((s, i) => {
  const y = bRowY(i);
  const grey = isRegex(s.model);
  for (const [key, st, dy, r] of ENDPOINTS) {
    svg.marker(scaleB(s[key]), y + dy, st.shape, r, grey ? COLORS.darkGrey : st.color,
      { cls: `marker ${key}` });
  }
});
svg.xAxis(B.x0, B.x1, B.axisY, [0.6, 0.7, 0.8, 0.9, 1.0], scaleB,
  { title: 'Proportion', fmtDp: 1, grid: [B.gridTop, B.axisY], titleDy: 5.0 });

// ------------------------------------------- panel c (recoverability by snippet count)
const agg = data.panels.c.aggregate_mean.points;
const CATS = ['0', '1', '2', '3+'];
const C = { x0: 93, x1: 163, top: 80.7, axisY: 112.8 };
const scaleCy = scaleLinear(0, 1.05, C.axisY, C.top);
const scaleCx = scaleLinear(0, CATS.length - 1, C.x0 + 5, C.x1 - 5);

const C_STYLE = {
  first_snippet: { color: COLORS.blue, shape: 'circle', dash: null, label: 'First snippet' },
  all_snippets: { color: COLORS.vermillion, shape: 'square', dash: null, label: 'All snippets' },
  mean_proportion: { color: COLORS.purple, shape: 'diamond', dash: '2.2,1.4', label: 'Mean recoverable proportion' },
};

svg.yAxis(C.x0, C.top, C.axisY, [0, 0.25, 0.5, 0.75, 1.0], scaleCy,
  { title: 'Mean recoverability across systems', titleX: 82.2, fmtDp: 2, grid: C.x1 });
// categorical x axis (composed locally; labels are "0","1","2","3+")
svg.line(C.x0, C.axisY, C.x1, C.axisY, { stroke: COLORS.axis, sw: STROKE.axis, cls: 'axis-x' });
CATS.forEach((cat, i) => {
  const x = scaleCx(i);
  svg.line(x, C.axisY, x, C.axisY + 1.6, { stroke: COLORS.axis, sw: STROKE.axis, cls: 'axis-x' });
  svg.text(x, C.axisY + 1.6 + SIZE.tick + 0.8, cat, { size: SIZE.tick, anchor: 'middle', cls: 'tick-label' });
});
svg.text((C.x0 + C.x1) / 2, C.axisY + 5.5 + SIZE.axisTitle,
  'Returned snippets per predicted FAIL (public synthetic layer)',
  { size: SIZE.axisTitle, anchor: 'middle', cls: 'axis-title' });

// lines + markers; null (undefined) values are skipped, so first_snippet and
// mean_proportion start at x="1" while all_snippets has a true defined 0 at x="0".
// Draw order puts first_snippet (blue circle) on top where values coincide.
for (const key of ['mean_proportion', 'all_snippets', 'first_snippet']) {
  const st = C_STYLE[key];
  const pts = CATS.map((cat, i) => ({ i, v: agg[cat][key] })).filter((p) => p.v != null);
  const d = pts.map((p, j) => `${j === 0 ? 'M' : 'L'} ${f3(scaleCx(p.i))} ${f3(scaleCy(p.v))}`).join(' ');
  svg.path(d, { stroke: st.color, sw: 1 * PT, dash: st.dash, cls: `line ${key}` });
  for (const p of pts) {
    svg.marker(scaleCx(p.i), scaleCy(p.v), st.shape, 1.2, st.color, { cls: `marker ${key}` });
  }
}

// legend below the plot (line + marker combos, composed locally), then the note
const cLegendItem = (x, y, key) => {
  const st = C_STYLE[key];
  const my = y - SIZE.legend * 0.32;
  svg.line(x - 2.2, my, x + 2.2, my, { stroke: st.color, sw: 1 * PT, dash: st.dash, cls: 'legend-line' });
  svg.marker(x, my, st.shape, 1.1, st.color, { cls: 'legend-marker' });
  svg.text(x + 3.4, y, st.label, { size: SIZE.legend, cls: 'legend-label' });
  return x + 3.4 + textWidth(st.label, SIZE.legend) + 5.5;
};
let cx = C.x0;
cx = cLegendItem(cx, 124.9, 'first_snippet');
cx = cLegendItem(cx, 124.9, 'all_snippets');
cLegendItem(C.x0, 127.9, 'mean_proportion');
svg.text(82, 131.3, 'Undefined values (no returned snippets) are omitted, never plotted as zero.',
  { size: 6.8 * PT, fill: COLORS.subtext, cls: 'note' });

const outPath = join(here, '../../supplementary_figures/Supplementary_Figure_S4.svg');
writeFileSync(outPath, svg.render());
console.log(outPath);
