// Supplementary Figure S5 — Human review, error taxonomy, and workflow.
// Panel a: targeted semantic review — three independent horizontal bars (not stacked).
// Panel b: primary error mechanism + actionability — two aligned count bar charts.
// Panel c: reviewer-facing audit workflow — four identical nodes with arrows.
// Data: ../data_json_or_csv/figS5.json (canonical, audit-locked). No numbers here.

import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Svg, scaleLinear, fmt, textWidth } from './svgkit.mjs';
import { COLORS, SIZE, STROKE, PT } from './style.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const data = JSON.parse(readFileSync(join(here, '../data_json_or_csv/figS5.json'), 'utf8'));

const W = 170, H = 112;
const svg = new Svg(W, H);

const SUB = 6.8 * PT; // smallest text used: wrapped category labels, notes

// Greedy word wrap (deterministic; uses svgkit's Arial width estimate).
function wrapText(str, maxW, sizeMm) {
  const words = String(str).split(' ');
  const lines = [];
  let cur = '';
  for (const w of words) {
    const cand = cur ? `${cur} ${w}` : w;
    if (cur && textWidth(cand, sizeMm) > maxW) { lines.push(cur); cur = w; }
    else cur = cand;
  }
  if (cur) lines.push(cur);
  return lines;
}

const LETTER_Y = 8;

// ================= panel a: targeted semantic review =================
const pa = data.panels.a;
const A_COLOR = { // per brief: targeted-review Yes/No semantics of Figure 2c
  'Lexically recoverable': COLORS.teal,
  'Semantically sufficient': COLORS.blue,
  'Recoverable but insufficient': COLORS.vermillion,
};
const aPlotX0 = 40, aPlotX1 = 64, aAxisY = 40.5, aGridTop = 16.5;
const aRowY = [20.5, 28, 35.5], aBarH = 4.4;
const aTicks = [0, 0.2, 0.4, 0.6, 0.8, 1.0];
const scaleA = scaleLinear(0, 1, aPlotX0, aPlotX1);

svg.panelLetter(4, LETTER_Y, 'a');
svg.panelTitle(8.2, LETTER_Y, pa.title);
svg.text(8.2, LETTER_Y + 3.8, `n = ${pa.n_total}`,
  { size: SUB, fill: COLORS.subtext, cls: 'n-note' });

for (const t of aTicks) {
  svg.line(scaleA(t), aGridTop, scaleA(t), aAxisY, { stroke: COLORS.grid, sw: STROKE.grid, cls: 'grid' });
}
svg.line(aPlotX0, aGridTop, aPlotX0, aAxisY, { stroke: COLORS.axis, sw: STROKE.axis, cls: 'axis-y' });

pa.bars.forEach((b, i) => {
  const cy = aRowY[i];
  const xEnd = scaleA(b.rate);
  svg.text(aPlotX0 - 2, cy + SIZE.label * 0.35, b.label,
    { size: SIZE.label, anchor: 'end', cls: 'row-label' });
  svg.rect(aPlotX0, cy - aBarH / 2, xEnd - aPlotX0, aBarH, { fill: A_COLOR[b.label], cls: 'bar' });
  const label = `${fmt(b.rate, 3)} (${b.n}/${pa.n_total})`;
  const dy = SIZE.label * 0.35;
  if (xEnd - aPlotX0 >= textWidth(label, SIZE.label) + 3) {
    // long bar: rate + count inside the bar end, white
    svg.text(xEnd - 1.3, cy + dy, label, { size: SIZE.label, anchor: 'end', fill: '#FFFFFF', cls: 'bar-label-in' });
  } else {
    // short bar: same format outside the bar end
    svg.text(xEnd + 1.3, cy + dy, label, { size: SIZE.label, cls: 'bar-label-out' });
  }
});
svg.xAxis(aPlotX0, aPlotX1, aAxisY, aTicks, scaleA,
  { title: `Proportion of the ${pa.n_total} reviewed citations`, fmtDp: 1 });

// ================= panel b: mechanism + actionability =================
const pb = data.panels.b;
const bAxisY = 49.5, bGridTop = 16.5, bRowY0 = 19, bPitch = 6.8, bBarH = 3.8;
const bTicks = [0, 50, 100, 150, 200];
const B_COLOR = [COLORS.blue, COLORS.teal]; // mechanism = deep blue, actionability = teal
const groupGeom = [
  { labelRight: 102.5, wrapW: 28.5, x0: 104, x1: 127, safeRight: 129 },
  { labelRight: 143.5, wrapW: 15, x0: 144.5, x1: 167.5, safeRight: 169 },
];

svg.panelLetter(74, LETTER_Y, 'b');

pb.groups.forEach((g, gi) => {
  const gm = groupGeom[gi];
  const scale = scaleLinear(0, 200, gm.x0, gm.x1);
  const color = B_COLOR[gi];

  // group header: bold title + "n = 214" note, centred over the plot
  const nNote = `n = ${g.n_total}`;
  const twT = textWidth(g.group, SIZE.axisTitle) * 1.12 + 0.4; // bold allowance
  const twN = textWidth(nNote, SUB);
  const hx = (gm.x0 + gm.x1) / 2 - (twT + 2.0 + twN) / 2;
  svg.text(hx, 13, g.group, { size: SIZE.axisTitle, weight: 'bold', cls: 'group-title' });
  svg.text(hx + twT + 2.0, 13, nNote, { size: SUB, fill: COLORS.subtext, cls: 'n-note' });

  for (const t of bTicks) {
    if (t === 0) continue; // coincides with the spine
    svg.line(scale(t), bGridTop, scale(t), bAxisY, { stroke: COLORS.grid, sw: STROKE.grid, cls: 'grid' });
  }
  svg.line(gm.x0, bGridTop, gm.x0, bAxisY, { stroke: COLORS.axis, sw: STROKE.axis, cls: 'axis-y' });

  g.bars.forEach((b, i) => {
    const cy = bRowY0 + bPitch * i;
    const xEnd = scale(b.n);
    const lines = wrapText(b.label, gm.wrapW, SUB);
    const ly = lines.length === 1 ? [cy + SUB * 0.35] : [cy - 1.4, cy + 1.4];
    lines.forEach((ln, k) => {
      svg.text(gm.labelRight, ly[k], ln, { size: SUB, anchor: 'end', cls: 'cat-label' });
    });
    svg.rect(gm.x0, cy - bBarH / 2, xEnd - gm.x0, bBarH, { fill: color, cls: 'bar' });
    const label = String(b.n);
    const dy = SIZE.label * 0.35;
    if (xEnd + 1.2 + textWidth(label, SIZE.label) <= gm.safeRight) {
      svg.text(xEnd + 1.2, cy + dy, label, { size: SIZE.label, cls: 'count-label' });
    } else {
      svg.text(xEnd - 1.2, cy + dy, label,
        { size: SIZE.label, anchor: 'end', fill: '#FFFFFF', cls: 'count-label-in' });
    }
  });
  svg.xAxis(gm.x0, gm.x1, bAxisY, bTicks, scale, { title: 'Count' });
});

// ================= panel c: reviewer-facing audit workflow =================
const pc = data.panels.c;
const cLetterY = 68;
const nodeW = 34, nodeH = 26, nodeY = 76, nodeX0 = 8, nodeGap = 8;
const arrowY = nodeY + nodeH / 2;

svg.panelLetter(4, cLetterY, 'c');
svg.panelTitle(8.2, cLetterY, pc.title);

pc.steps.forEach((s, i) => {
  const x0 = nodeX0 + (nodeW + nodeGap) * i;
  const cx = x0 + nodeW / 2;
  svg.rect(x0, nodeY, nodeW, nodeH,
    { fill: '#FFFFFF', stroke: COLORS.blue, sw: STROKE.node, rx: 1.5, cls: 'node' });
  svg.text(cx, nodeY + 7.6, String(s.n),
    { size: 12 * PT, weight: 'bold', anchor: 'middle', fill: COLORS.blue, cls: 'step-number' });
  svg.text(cx, nodeY + 13.8, s.title,
    { size: SIZE.axisTitle, weight: 'bold', anchor: 'middle', cls: 'step-title' });
  const lines = wrapText(s.sub, nodeW - 4, SUB);
  const ly = lines.length === 1 ? [nodeY + 20] : [nodeY + 18.6, nodeY + 21.4];
  lines.forEach((ln, k) => {
    svg.text(cx, ly[k], ln, { size: SUB, anchor: 'middle', fill: COLORS.subtext, cls: 'step-sub' });
  });
  if (i < pc.steps.length - 1) {
    svg.arrow(x0 + nodeW + 1, arrowY, x0 + nodeW + nodeGap - 1, arrowY,
      { sw: STROKE.arrow, head: 1.9, cls: 'flow-arrow' });
  }
});
svg.text(nodeX0 + (pc.steps.length * nodeW + (pc.steps.length - 1) * nodeGap) / 2, 108, pc.note,
  { size: SUB, anchor: 'middle', fill: COLORS.subtext, cls: 'flow-note' });

const outPath = join(here, '../../supplementary_figures/Supplementary_Figure_S5.svg');
writeFileSync(outPath, svg.render());
console.log(outPath);
