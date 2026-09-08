// Figure 2 — FAIL-class discrimination and evidence traceability.
// Panel a: paired-dot plot of macro-/micro-F1. Panel b: evidence endpoints on the
// same model rows. Panel c: 100% stacked bars of the targeted 96-output review.
// Data: ../data_json_or_csv/fig2.json (canonical, audit-locked). No numbers here.

import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Svg, scaleLinear } from './svgkit.mjs';
import { COLORS, SIZE, METRIC_STYLE, REVIEW_STYLE, STROKE, PT, isRegex } from './style.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const data = JSON.parse(readFileSync(join(here, '../data_json_or_csv/fig2.json'), 'utf8'));

const W = 180, H = 97;
const svg = new Svg(W, H);

// ---- geometry (mm) ----
const LETTER_Y = 8;
const PLOT_TOP = 19.5, PLOT_BOT = 75;
const AXIS_Y = 77.5;
const aLabelX = 4, aPlotX0 = 26, aPlotX1 = 74;         // panel a
const bLetterX = 78, bPlotX0 = 86, bPlotX1 = 136;      // panel b
const cLetterX = 140, cAxisX = 148.5;                  // panel c
const barXs = [157.5, 169.5], barW = 8;
const ROW_H = 5.15, ROW_Y0 = 20.7, REGEX_GAP = 2.3;
const n = data.panels.a.series.length;                 // 11
const rowY = (i) => ROW_Y0 + ROW_H * i + (i === n - 1 ? REGEX_GAP : 0);
const regexRowY = rowY(n - 1);
const sepY = (rowY(n - 2) + regexRowY) / 2;

const scaleA = scaleLinear(0.75, 1.00, aPlotX0, aPlotX1);
const scaleB = scaleLinear(0.55, 1.01, bPlotX0, bPlotX1);
const scaleC = scaleLinear(0, 1, PLOT_BOT, PLOT_TOP);

// ---- panel letters + titles ----
svg.panelLetter(aLabelX, LETTER_Y, 'a');
svg.panelTitle(aLabelX + 4.2, LETTER_Y, 'FAIL-class F1');
svg.panelLetter(bLetterX, LETTER_Y, 'b');
svg.panelTitle(bLetterX + 4.2, LETTER_Y, 'Evidence endpoints');
svg.panelLetter(cLetterX, LETTER_Y, 'c');
svg.panelTitle(cLetterX + 4.2, LETTER_Y, 'Targeted human review');
svg.text(cLetterX + 4.2, LETTER_Y + 3.8, `n = ${data.panels.c.n_total.value} targeted outputs`,
  { size: 6.8 * PT, fill: COLORS.subtext, cls: 'n-note' });

// ---- legend strips (top; two rows, spanning panels a+b) ----
let lx = aPlotX0;
lx = svg.legendItem(lx, 12.4, METRIC_STYLE.macroF1);
lx = svg.legendItem(lx, 12.4, METRIC_STYLE.microF1);
lx = aPlotX0;
lx = svg.legendItem(lx, 15.9, METRIC_STYLE.coverage);
lx = svg.legendItem(lx, 15.9, METRIC_STYLE.conditional);
lx = svg.legendItem(lx, 15.9, METRIC_STYLE.allSnippet);

// ---- faint row guides across panels a+b ----
for (let i = 0; i < n; i++) {
  svg.line(aPlotX0, rowY(i), bPlotX1, rowY(i), { stroke: '#EDF0F4', sw: 0.45 * PT, cls: 'row-guide' });
}
// Regex separator
svg.line(aPlotX0, sepY, bPlotX1, sepY, { stroke: COLORS.midGrey, sw: 0.6 * PT, dash: '2,1.4', cls: 'regex-separator' });

// ---- model labels (panel a only; rows shared with b) ----
data.panels.a.series.forEach((s, i) => {
  svg.text(aLabelX + 20.5, rowY(i) + SIZE.label * 0.35, s.model,
    { size: SIZE.label, anchor: 'end', cls: 'row-label' });
});

// ---- panel a: paired dots ----
data.panels.a.series.forEach((s, i) => {
  const y = rowY(i);
  const grey = isRegex(s.model);
  const cMacro = grey ? COLORS.darkGrey : METRIC_STYLE.macroF1.color;
  const cMicro = grey ? COLORS.darkGrey : METRIC_STYLE.microF1.color;
  const xM = scaleA(s.macro_f1), xm = scaleA(s.micro_f1);
  svg.line(xM, y, xm, y, { stroke: grey ? COLORS.midGrey : '#C3CAD3', sw: STROKE.connector, cls: 'pair-connector' });
  svg.marker(xM, y, METRIC_STYLE.macroF1.shape, 1.35, cMacro, { cls: 'marker macro-f1' });
  svg.marker(xm, y, METRIC_STYLE.microF1.shape, 1.25, cMicro, { cls: 'marker micro-f1' });
});
svg.xAxis(aPlotX0, aPlotX1, AXIS_Y, [0.75, 0.80, 0.85, 0.90, 0.95, 1.00], scaleA,
  { title: 'FAIL-class F1 among Gold-applicable pairs', fmtDp: 2, grid: [PLOT_TOP, AXIS_Y] });

// ---- panel b: evidence endpoints ----
const ENDPOINTS = [
  ['evidence_coverage', METRIC_STYLE.coverage, -1.55],
  ['conditional_item_recoverability', METRIC_STYLE.conditional, 0],
  ['all_snippet_recoverability', METRIC_STYLE.allSnippet, 1.55],
];
data.panels.b.series.forEach((s, i) => {
  const y = rowY(i);
  const grey = isRegex(s.model);
  for (const [key, st, dy] of ENDPOINTS) {
    svg.marker(scaleB(s[key]), y + dy, st.shape, 1.3, grey ? COLORS.darkGrey : st.color,
      { cls: `marker ${key}` });
  }
});
svg.xAxis(bPlotX0, bPlotX1, AXIS_Y, [0.6, 0.7, 0.8, 0.9, 1.0], scaleB,
  { title: 'Proportion', fmtDp: 1, grid: [PLOT_TOP, AXIS_Y] });

// ---- panel c: 100% stacked bars ----
const groups = data.panels.c.groups;
const nTotal = data.panels.c.n_total.value;
groups.forEach((g, gi) => {
  const bx = barXs[gi];
  let acc = 0;
  for (const seg of g.segments) {
    const frac = seg.n / nTotal;
    if (frac <= 0) { continue; } // true zero count: nothing to draw
    const key = seg.label.startsWith('Yes') ? 'yes' : seg.label.startsWith('Partial') ? 'partial' : 'no';
    const y0 = scaleC(acc), y1 = scaleC(acc + frac);
    const h = y0 - y1;
    svg.rect(bx - barW / 2, y1, barW, h, { fill: REVIEW_STYLE[key].color, cls: `segment ${key}` });
    const label = `${seg.n}/${nTotal}`;
    if (h >= 4.2) {
      svg.text(bx, (y0 + y1) / 2 + SIZE.label * 0.35, label,
        { size: SIZE.label, anchor: 'middle', fill: '#FFFFFF', weight: 'bold', cls: 'segment-label' });
    } else {
      // tiny top segment: label above the bar with a thin leader line
      const ly = PLOT_TOP - 2.6;
      svg.line(bx, y1, bx, ly + 1.0, { stroke: COLORS.subtext, sw: 0.5 * PT, cls: 'leader' });
      svg.text(bx, ly + 0.2, label, { size: 6.8 * PT, anchor: 'middle', cls: 'segment-label-out' });
    }
    acc += frac;
  }
  const words = g.group.split(' ');
  if (words.length > 1) {
    svg.text(bx, AXIS_Y + 3.2, words[0], { size: 6.8 * PT, anchor: 'middle', cls: 'group-label' });
    svg.text(bx, AXIS_Y + 6.4, words.slice(1).join(' '), { size: 6.8 * PT, anchor: 'middle', cls: 'group-label' });
  } else {
    svg.text(bx, AXIS_Y + 3.4, g.group, { size: 6.8 * PT, anchor: 'middle', cls: 'group-label' });
  }
});
svg.yAxis(cAxisX, PLOT_TOP, PLOT_BOT, [0, 0.5, 1.0], scaleC, { fmtDp: 1, tickSize: 1.4 });
svg.text(cAxisX - 7.6, (PLOT_TOP + PLOT_BOT) / 2, 'Proportion of targeted outputs',
  { size: SIZE.axisTitle, anchor: 'middle', rotate: -90, cls: 'axis-title' });
// segment key below the axis
let ly2 = 88.2;
for (const key of ['yes', 'partial', 'no']) {
  const st = REVIEW_STYLE[key];
  svg.rect(cLetterX + 4.2, ly2 - 2.2, 2.4, 2.4, { fill: st.color, cls: 'legend-swatch' });
  svg.text(cLetterX + 7.6, ly2, st.label, { size: 6.8 * PT, cls: 'legend-label' });
  ly2 += 3.4;
}

const outPath = join(here, '../../main_figures/Figure_2.svg');
writeFileSync(outPath, svg.render());
console.log(outPath);
