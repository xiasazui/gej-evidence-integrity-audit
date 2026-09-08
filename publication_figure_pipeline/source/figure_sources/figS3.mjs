// Supplementary Figure S3 — Applicability and predicted-NA sensitivity.
// Panel a: heatmap of predicted-NA rate on Gold-applicable pairs (model x rule H1–H6).
// Panel b: applicability discrimination scatter (Gold-NA specificity vs Gold-applicable
// sensitivity), expanded y axis. Panel c: per-system FAIL-class macro-F1 across the
// three predicted-NA policies. Data: ../data_json_or_csv/figS3.json (canonical,
// audit-locked). No numbers here.

import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Svg, scaleLinear, textWidth, fmt, heatColorOrange, heatTextColorOrange } from './svgkit.mjs';
import { COLORS, SIZE, STROKE, PT, METRIC_STYLE, isRegex } from './style.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const data = JSON.parse(readFileSync(join(here, '../data_json_or_csv/figS3.json'), 'utf8'));

const W = 170, H = 121;
const svg = new Svg(W, H);

const CELL_TEXT = 6.8 * PT;

// =================== panel a: predicted-NA heatmap (top, full width) ===================
const aLetterY = 8;
const aLabelRight = 27.5;
const aX0 = 29, aX1 = 149;
const aTop = 14.5, ROW_H = 4.6;
const aRows = data.panels.a.matrix.length;                    // 11
const rules = Object.keys(data.panels.a.matrix[0].values);    // H1..H6, JSON order
const aBot = aTop + ROW_H * aRows;
const cellW = (aX1 - aX0) / rules.length;
const cmax = data.panels.a.colorbar_max;

svg.panelLetter(4, aLetterY, 'a');
svg.panelTitle(8.2, aLetterY, data.panels.a.title);

data.panels.a.matrix.forEach((row, i) => {
  const y = aTop + ROW_H * i;
  svg.text(aLabelRight, y + ROW_H / 2 + SIZE.label * 0.35, row.model,
    { size: SIZE.label, anchor: 'end', cls: 'row-label' });
  rules.forEach((r, j) => {
    const v = row.values[r];
    const t = v / cmax;
    const x = aX0 + cellW * j;
    svg.rect(x, y, cellW, ROW_H,
      { fill: heatColorOrange(t), stroke: '#E8ECF0', sw: 0.45 * PT, cls: 'cell' });
    svg.text(x + cellW / 2, y + ROW_H / 2 + CELL_TEXT * 0.35, fmt(v, 3),
      { size: CELL_TEXT, anchor: 'middle', fill: heatTextColorOrange(t), cls: 'cell-value' });
  });
});
// Regex separator (baseline row sits last, visually set apart as in Figure 2)
svg.line(aX0, aBot - ROW_H, aX1, aBot - ROW_H,
  { stroke: COLORS.midGrey, sw: 0.6 * PT, dash: '2,1.4', cls: 'regex-separator' });
// column labels
rules.forEach((r, j) => {
  svg.text(aX0 + cellW * (j + 0.5), aBot + 3.6, r,
    { size: SIZE.label, anchor: 'middle', cls: 'col-label' });
});

// colorbar: sequential orange ramp 0 -> cmax, labelled 0 and exact max
const cbX = 153, cbW = 3.5, cbN = 60, cbH = aBot - aTop;
for (let i = 0; i < cbN; i++) {
  const t = 1 - (i + 0.5) / cbN;
  svg.rect(cbX, aTop + cbH * i / cbN, cbW, cbH / cbN, { fill: heatColorOrange(t), cls: 'colorbar-step' });
}
svg.rect(cbX, aTop, cbW, cbH, { fill: 'none', stroke: COLORS.axis, sw: 0.5 * PT, cls: 'colorbar-frame' });
svg.text(cbX + cbW + 1.2, aTop + 2.0, fmt(cmax, 3), { size: CELL_TEXT, cls: 'colorbar-label' });
svg.text(cbX + cbW + 1.2, aBot, '0', { size: CELL_TEXT, cls: 'colorbar-label' });

// =================== panels b + c: shared bottom-row geometry ===================
const bcLetterY = 76;
const plotTop = 82, plotBot = 105;

// =================== panel b: applicability discrimination ===================
const bX0 = 16, bX1 = 70;
const pts = data.panels.b.points;
const sxB = scaleLinear(0.88, 1.00, bX0, bX1);
const syB = scaleLinear(0.9955, 1.0002, plotBot, plotTop);

svg.panelLetter(4, bcLetterY, 'b');
svg.panelTitle(8.2, bcLetterY, data.panels.b.title);

svg.xAxis(bX0, bX1, plotBot, [0.88, 0.90, 0.92, 0.94, 0.96, 0.98, 1.00], sxB,
  { title: 'Gold-NA specificity', fmtDp: 2, grid: [plotTop, plotBot], titleDy: 6.0 });
svg.yAxis(bX0, plotTop, plotBot, [0.996, 0.997, 0.998, 0.999, 1.000], syB,
  { title: 'Gold-applicable sensitivity', titleX: 4.8, fmtDp: 3, grid: bX1 });

svg.text(bX0 + 1.6, plotBot - 2.6, 'Expanded y-axis',
  { size: CELL_TEXT, style: 'italic', fill: COLORS.subtext, cls: 'axis-note' });

pts.forEach(p => {
  const grey = isRegex(p.model);
  svg.marker(sxB(p.x_na_specificity), syB(p.y_applicability_sensitivity), 'circle', 1.05,
    grey ? COLORS.darkGrey : COLORS.blue, { cls: 'marker point' });
});

// Outlier labels with deterministic first-fit placement (fixed candidate order).
const LABELED = ['Regex', 'MiniMax', 'GPT-OSS-20B'];
const placedBoxes = [];
const pxys = pts.map(p => [sxB(p.x_na_specificity), syB(p.y_applicability_sensitivity)]);
pts.forEach((p, pi) => {
  if (!LABELED.includes(p.model)) return;
  const [px, py] = pxys[pi];
  const w = textWidth(p.model, CELL_TEXT);
  const candidates = [
    [2.0, 0.85, 'start'], [-2.0, 0.85, 'end'],
    [0, -2.3, 'middle'], [0, 3.6, 'middle'],
    [2.0, -2.0, 'start'], [-2.0, -2.0, 'end'],
    [2.0, 3.4, 'start'], [-2.0, 3.4, 'end'],
  ];
  for (const [dx, dy, anchor] of candidates) {
    const bx = px + dx, by = py + dy;
    const xL = anchor === 'start' ? bx : anchor === 'end' ? bx - w : bx - w / 2;
    const box = [xL - 0.3, by - CELL_TEXT - 0.3, xL + w + 0.3, by + 0.6];
    if (box[0] < bX0 + 0.4 || box[2] > bX1 - 0.4 || box[1] < plotTop + 0.4 || box[3] > plotBot - 0.4) continue;
    let ok = true;
    for (const [qx, qy] of pxys) {
      if (qx === px && qy === py) continue;
      if (qx > box[0] - 1.3 && qx < box[2] + 1.3 && qy > box[1] - 1.3 && qy < box[3] + 1.3) { ok = false; break; }
    }
    if (!ok) continue;
    for (const ob of placedBoxes) {
      if (box[0] < ob[2] && box[2] > ob[0] && box[1] < ob[3] && box[3] > ob[1]) { ok = false; break; }
    }
    if (!ok) continue;
    svg.text(bx, by, p.model, { size: CELL_TEXT, anchor, cls: 'point-label' });
    placedBoxes.push(box);
    break;
  }
});

// =================== panel c: predicted-NA policy sensitivity ===================
const cX0 = 92, cX1 = 138;
const series = data.panels.c.series;
const policies = Object.keys(series[0].values);               // as_pass, exclude, as_fail
const POLICY_LABEL = { as_pass: 'NA as PASS', exclude: 'exclude NA', as_fail: 'NA as FAIL' };
const catX = policies.map((_, i) => cX0 + 8 + i * ((cX1 - cX0 - 16) / (policies.length - 1)));
const syC = scaleLinear(0.78, 1.005, plotBot, plotTop);

svg.panelLetter(78, bcLetterY, 'c');
svg.panelTitle(82.2, bcLetterY, data.panels.c.title);

svg.yAxis(cX0, plotTop, plotBot, [0.8, 0.85, 0.9, 0.95, 1.0], syC,
  { title: 'FAIL-class macro-F1', titleX: 82.5, fmtDp: 2, grid: cX1 });
// categorical x axis (composed locally; svgkit xAxis is numeric)
svg.line(cX0, plotBot, cX1, plotBot, { stroke: COLORS.axis, sw: STROKE.axis, cls: 'axis-x' });
policies.forEach((p, i) => {
  svg.line(catX[i], plotBot, catX[i], plotBot + 1.6, { stroke: COLORS.axis, sw: STROKE.axis, cls: 'axis-x' });
  svg.text(catX[i], plotBot + 1.6 + SIZE.tick + 0.8, POLICY_LABEL[p],
    { size: SIZE.tick, anchor: 'middle', cls: 'tick-label' });
});

const linePath = (vals) => policies
  .map((p, i) => `${i ? 'L' : 'M'} ${catX[i].toFixed(3)} ${syC(vals[p]).toFixed(3)}`)
  .join(' ');

// 9 background LLM trajectories
series.filter(s => !isRegex(s.model) && s.model !== 'GPT-5.2').forEach(s => {
  svg.path(linePath(s.values), { stroke: COLORS.midGrey, sw: 0.6 * PT, cls: 'policy-line background' });
  policies.forEach((p, i) => {
    svg.marker(catX[i], syC(s.values[p]), 'circle', 0.55, COLORS.midGrey, { cls: 'marker background' });
  });
});
// GPT-5.2 emphasis
const gpt = series.find(s => s.model === 'GPT-5.2');
svg.path(linePath(gpt.values), { stroke: COLORS.vermillion, sw: 1.25 * PT, cls: 'policy-line gpt52' });
policies.forEach((p, i) => {
  svg.marker(catX[i], syC(gpt.values[p]), 'square', 0.95, COLORS.vermillion, { cls: 'marker gpt52' });
});
// Regex baseline
const rx = series.find(s => isRegex(s.model));
svg.path(linePath(rx.values), { stroke: COLORS.darkGrey, sw: 1.25 * PT, dash: '2.5,1.6', cls: 'policy-line regex' });
policies.forEach((p, i) => {
  svg.marker(catX[i], syC(rx.values[p]), 'circle', 0.95, COLORS.darkGrey, { cls: 'marker regex' });
});

// legend: own row below both bottom panels, centred on the canvas
const LEGEND = [
  { label: 'Other LLM systems', color: COLORS.midGrey, sw: 0.75 * PT, dash: null, shape: 'circle', mr: 0.55 },
  { label: 'GPT-5.2', color: COLORS.vermillion, sw: 1.25 * PT, dash: null, shape: 'square', mr: 0.95 },
  { label: METRIC_STYLE.regex.label, color: COLORS.darkGrey, sw: 1.25 * PT, dash: '2.5,1.6', shape: 'circle', mr: 0.95 },
];
const SAMP = 5, GAP_IN = 2, GAP_OUT = 6, legY = 118.2, legSize = SIZE.legend;
const totalW = LEGEND.reduce((acc, it) => acc + SAMP + GAP_IN + textWidth(it.label, legSize), 0)
  + GAP_OUT * (LEGEND.length - 1);
let lx = (W - totalW) / 2;
LEGEND.forEach(it => {
  const my = legY - legSize * 0.32;
  svg.line(lx, my, lx + SAMP, my, { stroke: it.color, sw: it.sw, dash: it.dash, cls: 'legend-line' });
  svg.marker(lx + SAMP / 2, my, it.shape, it.mr, it.color, { cls: 'legend-marker' });
  svg.text(lx + SAMP + GAP_IN, legY, it.label, { size: legSize, cls: 'legend-label' });
  lx += SAMP + GAP_IN + textWidth(it.label, legSize) + GAP_OUT;
});

const outPath = join(here, '../../supplementary_figures/Supplementary_Figure_S3.svg');
writeFileSync(outPath, svg.render());
console.log(outPath);
