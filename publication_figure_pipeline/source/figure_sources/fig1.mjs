// Figure 1 — Benchmark construction and operator-induced coupling.
// Panel a: benchmark construction flow (main flow + frozen policy/evaluation).
// Panel b: operator-induced coupling transitions among H2/H4/H5.
// Data: ../data_json_or_csv/fig1.json (canonical, audit-locked). No numbers here.

import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Svg, textWidth } from './svgkit.mjs';
import { COLORS, SIZE, STROKE, PT, VERDICT_STYLE } from './style.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const data = JSON.parse(readFileSync(join(here, '../data_json_or_csv/fig1.json'), 'utf8'));

const W = 180, H = 68;
const svg = new Svg(W, H);

// ---- geometry (mm) ----
const LETTER_Y = 7;
const HEAD = 7.5 * PT, SUB = 6.8 * PT;
const NODE_W = 26, NODE_H = 14, NODE_RX = 1.2;
const MAIN_Y = 15, AUX_Y = 42;
const mainCx = [16.5, 51.5, 86.5];                 // panel a main flow
const auxCx = [27, 62.5];                          // panel a aux flow
const B_X = 103;                                   // panel b letter x
const R = 7.5;                                     // panel b node radius
const POS = { H2: [122.5, 31], H4: [158.5, 31], H5: [140.5, 53] };
const EDGE_LABEL = {                             // anchor + position per directed edge
  'H2>H4': { x: 140.5, y: 27.6, anchor: 'middle' },
  'H2>H5': { x: 128.2, y: 42.6, anchor: 'end' },
  'H4>H5': { x: 152.8, y: 42.6, anchor: 'start' },
};
// Color + line-type double-encode the transition kind (vermillion solid / grey dashed).
const KIND_STYLE = {
  'PASS→FAIL': { color: VERDICT_STYLE.FAIL.color, dash: null },
  'PASS→NA': { color: COLORS.darkGrey, dash: '3,2' },
};

// Two-line word wrap: pick the split minimising the wider line; never start
// line 2 with a non-alphanumeric token; prefer breaking after an operator.
function wrap2(str, sizeMm) {
  const words = String(str).split(' ');
  if (words.length < 2) return [String(str)];
  let best = null;
  for (let i = 1; i < words.length; i++) {
    const l1 = words.slice(0, i).join(' '), l2 = words.slice(i).join(' ');
    if (!/^[A-Za-z0-9]/.test(l2)) continue;
    const score = Math.max(textWidth(l1, sizeMm), textWidth(l2, sizeMm)) - (/[+/·–-]$/.test(l1) ? 0.6 : 0);
    if (!best || score < best.score - 1e-9) best = { lines: [l1, l2], score };
  }
  return best ? best.lines : [String(str)];
}

// Identical rounded rect: bold headline + smaller two-line sub.
function flowNode(cx, y0, head, sub, border, fill, cls) {
  svg.rect(cx - NODE_W / 2, y0, NODE_W, NODE_H,
    { fill, stroke: border, sw: STROKE.node, rx: NODE_RX, cls: `flow-node ${cls}` });
  svg.text(cx, y0 + 4.9, head, { size: HEAD, weight: 'bold', anchor: 'middle', cls: 'node-head' });
  wrap2(sub, SUB).forEach((ln, i) => {
    svg.text(cx, y0 + 8.6 + 3.3 * i, ln, { size: SUB, anchor: 'middle', fill: COLORS.subtext, cls: 'node-sub' });
  });
}

// ---- panel letters + titles ----
svg.panelLetter(3.5, LETTER_Y, 'a');
svg.panelTitle(3.5 + 4.2, LETTER_Y, data.panels.a.title);
svg.panelLetter(B_X, LETTER_Y, 'b');
svg.panelTitle(B_X + 4.2, LETTER_Y, data.panels.b.title);
svg.text(B_X + 4.2, LETTER_Y + 4.3, data.panels.b.off_target_line,
  { size: SUB, fill: COLORS.subtext, cls: 'off-target' });

// ---- panel a: main flow (white fill, deep-blue border) ----
data.panels.a.main_flow.forEach((n, i) => {
  flowNode(mainCx[i], MAIN_Y, n.node, n.sub, COLORS.blue, '#FFFFFF', 'main');
});
const mainCy = MAIN_Y + NODE_H / 2;
for (let i = 0; i < mainCx.length - 1; i++) {
  svg.arrow(mainCx[i] + NODE_W / 2 + 0.6, mainCy, mainCx[i + 1] - NODE_W / 2 - 0.6, mainCy,
    { stroke: COLORS.axis, sw: STROKE.arrow, head: 2.2, cls: 'flow-arrow' });
}

// ---- panel a: aux flow (faint-grey fill, grey border) ----
data.panels.a.aux_flow.forEach((n, i) => {
  flowNode(auxCx[i], AUX_Y, n.node, n.sub, COLORS.darkGrey, COLORS.faintGrey, 'aux');
});
const auxCy = AUX_Y + NODE_H / 2;
svg.arrow(auxCx[0] + NODE_W / 2 + 0.6, auxCy, auxCx[1] - NODE_W / 2 - 0.6, auxCy,
  { stroke: COLORS.axis, sw: STROKE.arrow, head: 2.2, cls: 'flow-arrow' });
// light connector: 700 instances -> Frozen evaluation
svg.arrow(mainCx[2], MAIN_Y + NODE_H + 0.7, auxCx[1], AUX_Y - 0.7,
  { stroke: COLORS.midGrey, sw: 1 * PT, head: 1.8, cls: 'flow-connector' });
// footnote near Frozen evaluation
svg.text(auxCx[1], AUX_Y + NODE_H + 5.5, data.panels.a.footnote,
  { size: SUB, anchor: 'middle', fill: COLORS.subtext, cls: 'footnote' });

// ---- panel b: transition diagram ----
for (const e of data.panels.b.edges) {
  const [x1, y1] = POS[e.from], [x2, y2] = POS[e.to];
  const len = Math.hypot(x2 - x1, y2 - y1);
  const ux = (x2 - x1) / len, uy = (y2 - y1) / len;
  const st = KIND_STYLE[e.kind];
  svg.arrow(x1 + ux * (R + 0.6), y1 + uy * (R + 0.6), x2 - ux * (R + 1.1), y2 - uy * (R + 1.1),
    { stroke: st.color, sw: STROKE.arrow, dash: st.dash, head: 2.2, cls: 'edge' });
  const lp = EDGE_LABEL[`${e.from}>${e.to}`];
  svg.text(lp.x, lp.y, `${e.n} ${e.kind}`, { size: SIZE.label, anchor: lp.anchor, cls: 'edge-label' });
}
for (const name of data.panels.b.nodes) {
  const [cx, cy] = POS[name];
  svg.marker(cx, cy, 'circle', R, '#FFFFFF', { stroke: COLORS.darkGrey, sw: STROKE.node, cls: 'coupling-node' });
  svg.text(cx, cy + SIZE.label * 0.36, name, { size: SIZE.label, weight: 'bold', anchor: 'middle', cls: 'node-label' });
}
// compact line-style key (kinds in JSON edge order); 6 mm swatches so the
// dashed style shows a full dash–gap–dash cycle.
const kinds = [...new Set(data.panels.b.edges.map((e) => e.kind))];
const SW = 6, KEY_Y = 64.3;
const items = kinds.map((k) => ({ k, w: SW + 1.6 + textWidth(k, SIZE.legend) }));
const totalW = items.reduce((a, it) => a + it.w, 0) + 5.5 * (items.length - 1);
let kx = POS.H5[0] - totalW / 2;
for (const it of items) {
  const st = KIND_STYLE[it.k];
  svg.line(kx, KEY_Y - SIZE.legend * 0.32, kx + SW, KEY_Y - SIZE.legend * 0.32,
    { stroke: st.color, sw: STROKE.arrow, dash: st.dash, cls: 'key-swatch' });
  svg.text(kx + SW + 1.6, KEY_Y, it.k, { size: SIZE.legend, cls: 'key-label' });
  kx += it.w + 5.5;
}

const outPath = join(here, '../../main_figures/Figure_1.svg');
writeFileSync(outPath, svg.render());
console.log(outPath);
