// Figure 3 — FAIL-class and applicability performance.
// Panel a: per-rule FAIL-class F1 heatmap (11 models x 6 audit rules) + colorbar.
// Panel b: Gold-applicable discrimination (macro-specificity vs macro-sensitivity).
// Panel c: applicability classification on an expanded y-axis. Regex always dark grey.
// Data: ../data_json_or_csv/fig3.json (canonical, audit-locked). No numbers here.

import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Svg, scaleLinear, heatColor, heatTextColor, fmt, textWidth } from './svgkit.mjs';
import { COLORS, SIZE, PT, isRegex } from './style.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const data = JSON.parse(readFileSync(join(here, '../data_json_or_csv/fig3.json'), 'utf8'));

const W = 180, H = 78;
const svg = new Svg(W, H);

// ---- geometry (mm) ----
const LETTER_Y = 8;
const PLOT_TOP = 15, PLOT_BOT = 62.5, AXIS_Y = PLOT_BOT;
const LABEL_68 = 6.8 * PT;
const LABEL_DY = LABEL_68 * 0.34;            // baseline offset: small label centred on its point

// panel a — heatmap
const aLetterX = 4, rowLabelX = 25;
const HM_X0 = 27, CELL_W = 8.5, HM_Y0 = 14, ROW_H = 4.6;
const matrix = data.panels.a.matrix;         // 11 rows, canonical order (Regex last)
const rules = Object.keys(matrix[0].f1);     // H1..H6, JSON order
const HM_X1 = HM_X0 + CELL_W * rules.length;
const HM_Y1 = HM_Y0 + ROW_H * matrix.length;
const CB_X = HM_X1 + 2.5, CB_W = 2.2, CB_Y0 = 17, CB_H = 30;

// panels b + c — scatter plots
const B_AXIS_X = 106.5, B_PLOT_X1 = 135.5;
const C_AXIS_X = 154.5, C_PLOT_X1 = 178;

// ---- panel letters + titles ----
// Long bold titles: b/c headers are right-anchored from the canvas edge using a
// deterministic width estimate (calibrated against Chrome's Arial bold metrics),
// so the two titles + letters can never collide or clip at the right edge.
svg.panelLetter(aLetterX, LETTER_Y, 'a');
svg.panelTitle(aLetterX + 4.2, LETTER_Y, data.panels.a.title);
const BOLD_W = 1.13;                         // Arial bold ≈ +9..13% over the textWidth estimate
const wB = textWidth(data.panels.b.title, SIZE.panelTitle) * BOLD_W;
const wC = textWidth(data.panels.c.title, SIZE.panelTitle) * BOLD_W;
const cTitleX = 179.6 - wC;
const cLetterX = cTitleX - 4.2;
const bTitleX = cLetterX - 2.2 - wB;
const bLetterX = bTitleX - 4.2;
svg.panelLetter(bLetterX, LETTER_Y, 'b');
svg.panelTitle(bTitleX, LETTER_Y, data.panels.b.title);
svg.panelLetter(cLetterX, LETTER_Y, 'c');
svg.panelTitle(cTitleX, LETTER_Y, data.panels.c.title);

// ---- panel a: per-rule FAIL-class F1 heatmap ----
rules.forEach((r, j) => {
  svg.text(HM_X0 + CELL_W * (j + 0.5), HM_Y0 - 1.2, r,
    { size: SIZE.label, anchor: 'middle', cls: 'col-label' });
});
matrix.forEach((row, i) => {
  const cy = HM_Y0 + ROW_H * (i + 0.5);
  svg.text(rowLabelX, cy + SIZE.label * 0.35, row.model,
    { size: SIZE.label, anchor: 'end', fill: isRegex(row.model) ? COLORS.darkGrey : COLORS.text, cls: 'row-label' });
  rules.forEach((r, j) => {
    const v = row.f1[r];
    const cellX = HM_X0 + CELL_W * j, cellY = HM_Y0 + ROW_H * i;
    svg.rect(cellX, cellY, CELL_W, ROW_H,
      { fill: heatColor(v), stroke: '#FFFFFF', sw: 0.5 * PT, cls: 'cell' });
    svg.text(cellX + CELL_W / 2, cy + LABEL_68 * 0.35, fmt(v, 3),
      { size: LABEL_68, anchor: 'middle', fill: heatTextColor(v), cls: 'cell-value' });
  });
});
svg.text((HM_X0 + HM_X1) / 2, HM_Y1 + 5.0, 'Audit rule',
  { size: SIZE.axisTitle, anchor: 'middle', cls: 'axis-title' });

// colorbar: sequential blue 0 -> 1 (the only gradient permitted)
const gradId = 'fig3-heat-gradient';
svg.defs.push(`<linearGradient id="${gradId}" x1="0" y1="1" x2="0" y2="0">` +
  [0, 0.25, 0.5, 0.75, 1].map((t) => `<stop offset="${t}" stop-color="${heatColor(t)}"/>`).join('') +
  `</linearGradient>`);
svg.rect(CB_X, CB_Y0, CB_W, CB_H,
  { fill: `url(#${gradId})`, stroke: COLORS.axis, sw: 0.5 * PT, cls: 'colorbar' });
[['1', CB_Y0], ['0.5', CB_Y0 + CB_H / 2], ['0', CB_Y0 + CB_H]].forEach(([s, y]) => {
  svg.text(CB_X + CB_W + 0.9, y + SIZE.tick * 0.35, s, { size: SIZE.tick, cls: 'cb-tick' });
});
svg.text(CB_X + CB_W + 6.9, CB_Y0 + CB_H / 2, 'FAIL-class F1',
  { size: SIZE.axisTitle, anchor: 'middle', rotate: -90, cls: 'axis-title' });

// ---- panel b: Gold-applicable discrimination ----
const bPts = data.panels.b.points;
const bX = scaleLinear(0.855, 1.008, B_AXIS_X, B_PLOT_X1);
const bY = scaleLinear(0.80, 1.005, PLOT_BOT, PLOT_TOP);
svg.xAxis(B_AXIS_X, B_PLOT_X1, AXIS_Y, [0.9, 0.95, 1.0], bX,
  { title: 'FAIL-class macro-specificity', fmtDp: 2, grid: [PLOT_TOP, AXIS_Y] });
svg.yAxis(B_AXIS_X, PLOT_TOP, PLOT_BOT, [0.8, 0.85, 0.9, 0.95, 1.0], bY,
  { title: 'FAIL-class macro-sensitivity', titleX: 97.5, fmtDp: 2, grid: B_PLOT_X1 });
bPts.forEach((p) => {
  const grey = isRegex(p.model);
  svg.marker(bX(p.x_specificity), bY(p.y_sensitivity), 'circle', 1.5,
    grey ? COLORS.darkGrey : COLORS.blue, { cls: grey ? 'point regex' : 'point llm' });
});
// only the two clear outliers are labelled; fixed offsets verified against all points
const bByModel = Object.fromEntries(bPts.map((p) => [p.model, p]));
svg.text(bX(bByModel['GPT-5.2'].x_specificity) + 2.0,
  bY(bByModel['GPT-5.2'].y_sensitivity) + LABEL_DY, 'GPT-5.2', { size: LABEL_68, cls: 'point-label' });
svg.text(bX(bByModel.Regex.x_specificity) - 2.0,
  bY(bByModel.Regex.y_sensitivity) + LABEL_DY, 'Regex',
  { size: LABEL_68, anchor: 'end', cls: 'point-label' });

// ---- panel c: applicability classification (expanded y-axis) ----
const cPts = data.panels.c.points;
const cX = scaleLinear(0.865, 1.008, C_AXIS_X, C_PLOT_X1);
const cY = scaleLinear(0.9957, 1.0005, PLOT_BOT, PLOT_TOP); // data min 0.996094 - small pad -> 1.0005
svg.xAxis(C_AXIS_X, C_PLOT_X1, AXIS_Y, [0.9, 0.95, 1.0], cX,
  { title: 'Gold-NA specificity', fmtDp: 2, grid: [PLOT_TOP, AXIS_Y] });
svg.yAxis(C_AXIS_X, PLOT_TOP, PLOT_BOT, [0.996, 0.998, 1.0], cY,
  { title: 'Gold-applicable sensitivity', titleX: 143.5, fmtDp: 3, grid: C_PLOT_X1 });
cPts.forEach((p) => {
  const grey = isRegex(p.model);
  svg.marker(cX(p.x_na_specificity), cY(p.y_applicability_sensitivity), 'circle', 1.5,
    grey ? COLORS.darkGrey : COLORS.blue, { cls: grey ? 'point regex' : 'point llm' });
});
if (data.panels.c.expanded_y) {
  svg.text(C_AXIS_X + 1.3, PLOT_TOP + 2.6, 'Expanded y-axis',
    { size: LABEL_68, style: 'italic', fill: COLORS.subtext, cls: 'axis-note' });
}
// only the clearly separated points are labelled. GPT-OSS-20B hugs the left spine, so
// its label drops straight down with a thin leader; MiniMax and Regex label to the left.
const cByModel = Object.fromEntries(cPts.map((p) => [p.model, p]));
const p20x = cX(cByModel['GPT-OSS-20B'].x_na_specificity);
const p20y = cY(cByModel['GPT-OSS-20B'].y_applicability_sensitivity);
svg.line(p20x, p20y + 1.8, p20x, p20y + 9.2, { stroke: COLORS.subtext, sw: 0.5 * PT, cls: 'leader' });
svg.text(p20x - 1.2, p20y + 12.0, 'GPT-OSS-20B', { size: LABEL_68, cls: 'point-label' });
for (const name of ['MiniMax', 'Regex']) {
  const p = cByModel[name];
  svg.text(cX(p.x_na_specificity) - 2.0, cY(p.y_applicability_sensitivity) + LABEL_DY, name,
    { size: LABEL_68, anchor: 'end', cls: 'point-label' });
}

const outPath = join(here, '../../main_figures/Figure_3.svg');
writeFileSync(outPath, svg.render());
console.log(outPath);
