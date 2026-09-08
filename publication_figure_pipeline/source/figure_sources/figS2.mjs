// Supplementary Figure S2 — Model discrimination diagnostics.
// Panel a: model-level FAIL-class specificity/sensitivity scatter. Panels b/c: per-rule
// FAIL sensitivity / specificity heatmaps on one shared 0-1 sequential blue scale.
// Data: ../data_json_or_csv/figS2.json (canonical, audit-locked). No numbers here.

import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Svg, scaleLinear, fmt, heatColor, heatTextColor } from './svgkit.mjs';
import { COLORS, SIZE, STROKE, PT, isRegex } from './style.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const data = JSON.parse(readFileSync(join(here, '../data_json_or_csv/figS2.json'), 'utf8'));

const W = 170, H = 119;
const svg = new Svg(W, H);

// ---- geometry (mm) ----
const LETTER_Y = 8;
const aLabelX = 4, aPlotX0 = 17, aPlotX1 = 166, aTop = 14, aAxisY = 42; // panel a scatter
const HM_LETTER_Y = 58, COL_LABEL_Y = 64, HM_TOP = 66;                  // heatmaps
const ROW_H = 4.5, CELL_W = 9.6, CELL_GAP = 0.24;
const bLabelX = 4, bX0 = 23;         // panel b heatmap (model labels at left)
const cLabelX = 88.5, cX0 = 97;      // panel c heatmap (rows strictly aligned with b)
const CB_X = 157.6, CB_W = 3.2, CB_Y0 = 75.75, CB_Y1 = 105.75;         // shared colorbar

// ---- panel a: model-level discrimination ----
svg.panelLetter(aLabelX, LETTER_Y, 'a');
svg.panelTitle(aLabelX + 4.2, LETTER_Y, data.panels.a.title);
const pts = data.panels.a.points;
const sx = scaleLinear(0.86, 1.00, aPlotX0, aPlotX1);
const sy = scaleLinear(0.80, 1.005, aAxisY, aTop);
svg.xAxis(aPlotX0, aPlotX1, aAxisY, [0.88, 0.90, 0.92, 0.94, 0.96, 0.98, 1.00], sx,
  { title: 'FAIL-class macro-specificity', fmtDp: 2, titleDy: 7.5, grid: [aTop, aAxisY] });
svg.yAxis(aPlotX0, aTop, aAxisY, [0.80, 0.85, 0.90, 0.95, 1.00], sy,
  { title: 'FAIL-class macro-sensitivity', fmtDp: 2, titleX: 8.6, grid: aPlotX1 });
for (const p of pts) {
  const grey = isRegex(p.model);
  svg.marker(sx(p.x_specificity), sy(p.y_sensitivity), 'circle', 1.35,
    grey ? COLORS.darkGrey : COLORS.blue, { cls: 'marker model-point' });
}
// only the two diagnostic outliers are labeled: GPT-5.2 (low specificity), Regex (low sensitivity)
const gpt = pts.find(p => p.model === 'GPT-5.2');
const rgx = pts.find(p => p.model === 'Regex');
svg.text(sx(gpt.x_specificity) - 2.0, sy(gpt.y_sensitivity) + 2.8, gpt.model,
  { size: 6.8 * PT, anchor: 'end', cls: 'point-label' });
svg.text(sx(rgx.x_specificity) - 2.0, sy(rgx.y_sensitivity) + 0.85, rgx.model,
  { size: 6.8 * PT, anchor: 'end', fill: COLORS.darkGrey, cls: 'point-label' });

// ---- panels b/c: per-rule heatmaps, rows strictly aligned ----
const rules = Object.keys(data.panels.b.matrix[0].values); // H1..H6, canonical order
function heatmap(x0, matrix, withRowLabels, clsPrefix) {
  rules.forEach((r, j) => {
    svg.text(x0 + CELL_W * (j + 0.5), COL_LABEL_Y, r,
      { size: SIZE.label, anchor: 'middle', cls: 'col-label' });
  });
  matrix.forEach((m, i) => {
    const ry = HM_TOP + ROW_H * i, cy = ry + ROW_H / 2;
    if (withRowLabels) {
      svg.text(x0 - 1.5, cy + SIZE.label * 0.35, m.model,
        { size: SIZE.label, anchor: 'end',
          fill: isRegex(m.model) ? COLORS.darkGrey : COLORS.text, cls: 'row-label' });
    }
    rules.forEach((r, j) => {
      const v = m.values[r];
      const cx = x0 + CELL_W * j;
      svg.rect(cx + CELL_GAP / 2, ry + CELL_GAP / 2, CELL_W - CELL_GAP, ROW_H - CELL_GAP,
        { fill: heatColor(v), cls: `cell ${clsPrefix}` });
      svg.text(cx + CELL_W / 2, cy + SIZE.label * 0.35, fmt(v, 2),
        { size: SIZE.label, anchor: 'middle', fill: heatTextColor(v), cls: 'cell-label' });
    });
  });
}
svg.panelLetter(bLabelX, HM_LETTER_Y, 'b');
svg.panelTitle(bLabelX + 4.2, HM_LETTER_Y, data.panels.b.title);
svg.panelLetter(cLabelX, HM_LETTER_Y, 'c');
svg.panelTitle(cLabelX + 4.2, HM_LETTER_Y, data.panels.c.title);
heatmap(bX0, data.panels.b.matrix, true, 'sensitivity');
heatmap(cX0, data.panels.c.matrix, false, 'specificity');

// ---- shared compact colorbar (0-1, same sequential blue scale as the cells) ----
const stops = [];
for (let i = 0; i <= 10; i++) stops.push(`<stop offset="${i * 10}%" stop-color="${heatColor(i / 10)}"/>`);
svg.defs.push(`<linearGradient id="cbgrad" x1="0%" y1="100%" x2="0%" y2="0%">${stops.join('')}</linearGradient>`);
svg.rect(CB_X, CB_Y0, CB_W, CB_Y1 - CB_Y0,
  { fill: 'url(#cbgrad)', stroke: COLORS.axis, sw: 0.6 * PT, cls: 'colorbar' });
const cby = scaleLinear(0, 1, CB_Y1, CB_Y0);
for (const t of [0, 0.5, 1]) {
  svg.line(CB_X + CB_W, cby(t), CB_X + CB_W + 1.2, cby(t),
    { stroke: COLORS.axis, sw: STROKE.axis, cls: 'cb-tick' });
  svg.text(CB_X + CB_W + 2.2, cby(t) + SIZE.tick * 0.36, fmt(t, 2),
    { size: SIZE.tick, cls: 'cb-tick-label' });
}

const outPath = join(here, '../../supplementary_figures/Supplementary_Figure_S2.svg');
writeFileSync(outPath, svg.render());
console.log(outPath);
