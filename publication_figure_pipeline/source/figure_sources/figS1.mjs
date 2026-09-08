// Supplementary Figure S1 — Benchmark and Gold-label structure.
// Panel a: case-level audit burden (Gold FAIL rules per case). Panel b: PASS/FAIL/NA
// composition of the rule-instance pairs for each frozen rule.
// Data: ../data_json_or_csv/figS1.json (canonical, audit-locked). No numbers here.

import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Svg, scaleLinear, fmtInt, textWidth } from './svgkit.mjs';
import { COLORS, SIZE, STROKE, PT, VERDICT_STYLE } from './style.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const data = JSON.parse(readFileSync(join(here, '../data_json_or_csv/figS1.json'), 'utf8'));

const W = 170, H = 63;
const svg = new Svg(W, H);

// ---- geometry (mm) ----
const LETTER_Y = 8;
const PLOT_TOP = 15, AXIS_Y = 51;
const aLabelX = 4, aPlotX0 = 14, aPlotX1 = 53;   // panel a (~35% width)
const bLabelX = 62, bPlotX0 = 70, bPlotX1 = 164; // panel b (~65% width)
const SEGS = ['PASS', 'FAIL', 'NA'];

// ---- panel letters + titles ----
svg.panelLetter(aLabelX, LETTER_Y, 'a');
svg.panelTitle(aLabelX + 4.2, LETTER_Y, data.panels.a.title);
svg.panelLetter(bLabelX, LETTER_Y, 'b');
svg.panelTitle(bLabelX + 4.2, LETTER_Y, data.panels.b.title);

// ---- panel a: vertical bars ----
const bars = data.panels.a.bars;
const ay = scaleLinear(0, 550, AXIS_Y, PLOT_TOP);
const ax = scaleLinear(-0.5, bars.length - 0.5, aPlotX0, aPlotX1);
const BAR_W = 4.6;
bars.forEach((b, i) => {
  const cx = ax(i), top = ay(b.cases);
  svg.rect(cx - BAR_W / 2, top, BAR_W, AXIS_Y - top, { fill: COLORS.blue, cls: 'bar' });
  svg.text(cx, top - 1.2, fmtInt(b.cases), { size: SIZE.label, anchor: 'middle', cls: 'bar-count' });
});
svg.yAxis(aPlotX0, PLOT_TOP, AXIS_Y, [0, 100, 200, 300, 400, 500], ay, { title: 'Cases', titleX: 5.6 });
svg.xAxis(aPlotX0, aPlotX1, AXIS_Y, bars.map(b => b.fail_rules), ax,
  { title: 'Gold FAIL rules per case', titleDy: 7.5 });

// ---- panel b: stacked horizontal count bars ----
const rows = data.panels.b.rows;
const ruleN = SEGS.reduce((s, k) => s + rows[0][k], 0);   // rule-instance pairs per rule
const bx = scaleLinear(0, ruleN, bPlotX0, bPlotX1);
const bTop = 16, ROW_H = (AXIS_Y - bTop) / rows.length, BAR_H = 3.4;
// subsidiary vertical gridlines (bars drawn on top)
for (let t = 100; t < ruleN; t += 100) {
  svg.line(bx(t), bTop, bx(t), AXIS_Y, { stroke: COLORS.grid, sw: STROKE.grid, cls: 'grid' });
}
rows.forEach((r, i) => {
  const cy = bTop + ROW_H * (i + 0.5);
  svg.text(bPlotX0 - 1.5, cy + SIZE.label * 0.35, r.rule,
    { size: SIZE.label, anchor: 'end', cls: 'row-label' });
  let acc = 0;
  for (const key of SEGS) {
    const n = r[key];
    if (n <= 0) { continue; } // true zero count: nothing to draw
    const x0 = bx(acc), x1 = bx(acc + n);
    svg.rect(x0, cy - BAR_H / 2, x1 - x0, BAR_H, { fill: VERDICT_STYLE[key].color, cls: `segment ${key.toLowerCase()}` });
    if (x1 - x0 >= 4.5) {     // count inside the segment; skip only if too small to fit
      svg.text((x0 + x1) / 2, cy + SIZE.label * 0.35, fmtInt(n),
        { size: SIZE.label, anchor: 'middle', weight: key === 'NA' ? 'normal' : 'bold',
          fill: key === 'NA' ? COLORS.text : '#FFFFFF', cls: 'segment-label' });
    } else {
      // segment too narrow for an inside count (e.g. H3 PASS = 4): thin leader to an
      // outside label sitting in the inter-row gap, so every count stays printed.
      const segCx = (x0 + x1) / 2;
      const up = i < rows.length - 1;                 // last row would go below instead
      const gapC = cy + (up ? -1 : 1) * (ROW_H + BAR_H) / 4;
      const labelY = gapC + SIZE.label * 0.30;
      const labelX = Math.max(segCx + 2.4, x1 + 1.4);
      const kneeY = cy + (up ? -1 : 1) * (BAR_H / 2 + 0.15);
      svg.line(segCx, kneeY, labelX - 0.8, labelY - SIZE.label * 0.30,
        { stroke: COLORS.subtext, sw: 0.3 * PT, cls: 'leader' });
      svg.text(labelX, labelY, fmtInt(n),
        { size: SIZE.label, anchor: 'start', weight: 'bold', fill: COLORS.text, cls: 'segment-label outside' });
    }
    acc += n;
  }
});
svg.line(bPlotX0, bTop, bPlotX0, AXIS_Y, { stroke: COLORS.axis, sw: STROKE.axis, cls: 'axis-y' });
const xTicks = [];
for (let t = 0; t <= ruleN; t += 100) xTicks.push(t);
svg.xAxis(bPlotX0, bPlotX1, AXIS_Y, xTicks, bx,
  { title: `Gold rule-instance pairs (n = ${ruleN} per rule)`, titleDy: 7.5 });

// ---- compact horizontal legend (top-right of panel b, clear of data) ----
const LG_Y = 12.3, SW = 2.4, LG_GAP = 3.4;
const items = SEGS.map(k => ({
  color: VERDICT_STYLE[k].color, label: VERDICT_STYLE[k].label,
  w: SW + 0.9 + textWidth(VERDICT_STYLE[k].label, SIZE.legend),
}));
let lx = bPlotX1 - (items.reduce((s, it) => s + it.w, 0) + LG_GAP * (items.length - 1));
for (const it of items) {
  svg.rect(lx, LG_Y - 2.2, SW, SW, { fill: it.color, cls: 'legend-swatch' });
  svg.text(lx + SW + 0.9, LG_Y, it.label, { size: SIZE.legend, cls: 'legend-label' });
  lx += it.w + LG_GAP;
}

const outPath = join(here, '../../supplementary_figures/Supplementary_Figure_S1.svg');
writeFileSync(outPath, svg.render());
console.log(outPath);
