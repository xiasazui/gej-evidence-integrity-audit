// svgkit.mjs — minimal deterministic SVG builder for scientific figures.
// All geometry in millimetres; one user unit = 1 mm. No randomness, no timers:
// identical input produces byte-identical SVG.

import { FONT, SIZE, COLORS, STROKE, PT } from './style.mjs';

// Scientific Reports requests lines of at least 1 pt at final size.  Clamp all
// stroked primitives here so local plot code cannot accidentally emit thinner
// grid, connector, border, or marker-outline strokes.
const MIN_STROKE = 1 * PT;
const safeStroke = (sw) => Math.max(Number(sw), MIN_STROKE);

export function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function fmt(v, dp = 3) {
  return Number(v).toFixed(dp);
}

export function fmtInt(v) {
  return Math.round(v).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

export function scaleLinear(d0, d1, r0, r1) {
  const k = (r1 - r0) / (d1 - d0);
  return (v) => r0 + (v - d0) * k;
}

// Rough Arial text-width estimate (mm) for label-collision logic only;
// rendering never depends on it (text-anchor handles alignment).
const WIDE = 'MW@#%&', NARROW = 'iljtf.,:;\'!|()[]/\\ ';
export function textWidth(str, sizeMm) {
  let em = 0;
  for (const ch of String(str)) {
    if (WIDE.includes(ch)) em += 0.72;
    else if (NARROW.includes(ch)) em += 0.30;
    else if (ch >= '0' && ch <= '9') em += 0.56;
    else if (ch === ch.toUpperCase() && ch !== ch.toLowerCase()) em += 0.62;
    else em += 0.50;
  }
  return em * sizeMm;
}

let uidCounter = 0;
export function uid(prefix) { return `${prefix}-${++uidCounter}`; }

export class Svg {
  constructor(widthMm, heightMm) {
    this.w = widthMm; this.h = heightMm;
    this.parts = [];
    this.defs = [];
  }
  add(s) { this.parts.push(s); return this; }
  raw(s) { return this.add(s); }
  open(cls, extra = '') { this.parts.push(`<g${cls ? ` class="${cls}"` : ''}${extra ? ' ' + extra : ''}>`); return this; }
  close() { this.parts.push('</g>'); return this; }

  rect(x, y, w, h, { fill = 'none', stroke = null, sw = STROKE.node, rx = 0, cls = null, id = null } = {}) {
    this.add(`<rect${id ? ` id="${id}"` : ''}${cls ? ` class="${cls}"` : ''} x="${f3(x)}" y="${f3(y)}" width="${f3(w)}" height="${f3(h)}"${rx ? ` rx="${f3(rx)}"` : ''} fill="${fill}"${stroke ? ` stroke="${stroke}" stroke-width="${f3(safeStroke(sw))}"` : ''}/>`);
    return this;
  }
  line(x1, y1, x2, y2, { stroke = COLORS.axis, sw = STROKE.axis, dash = null, cap = 'butt', cls = null } = {}) {
    this.add(`<line${cls ? ` class="${cls}"` : ''} x1="${f3(x1)}" y1="${f3(y1)}" x2="${f3(x2)}" y2="${f3(y2)}" stroke="${stroke}" stroke-width="${f3(safeStroke(sw))}"${dash ? ` stroke-dasharray="${dash}"` : ''} stroke-linecap="${cap}"/>`);
    return this;
  }
  path(d, { fill = 'none', stroke = null, sw = STROKE.axis, dash = null, cls = null, cap = 'butt', join = 'miter' } = {}) {
    this.add(`<path${cls ? ` class="${cls}"` : ''} d="${d}" fill="${fill}"${stroke ? ` stroke="${stroke}" stroke-width="${f3(safeStroke(sw))}" stroke-linecap="${cap}" stroke-linejoin="${join}"${dash ? ` stroke-dasharray="${dash}"` : ''}` : ''}/>`);
    return this;
  }
  text(x, y, str, { size = SIZE.label, weight = 'normal', anchor = 'start', fill = COLORS.text,
                    style = null, rotate = null, cls = null, id = null, spacing = null } = {}) {
    const tr = rotate ? ` transform="rotate(${rotate} ${f3(x)} ${f3(y)})"` : '';
    this.add(`<text${id ? ` id="${id}"` : ''}${cls ? ` class="${cls}"` : ''} x="${f3(x)}" y="${f3(y)}" font-family="${FONT}" font-size="${f3(size)}" font-weight="${weight}"${style ? ` font-style="${style}"` : ''} text-anchor="${anchor}" fill="${fill}"${spacing ? ` letter-spacing="${spacing}"` : ''}${tr}>${esc(str)}</text>`);
    return this;
  }
  // Filled data marker centred at (x, y); r ≈ half-size in mm.
  marker(x, y, shape, r, fill, { stroke = null, sw = 0.6 * PT, cls = null } = {}) {
    const c = cls ? ` class="${cls}"` : '';
    const st = stroke ? ` stroke="${stroke}" stroke-width="${f3(safeStroke(sw))}"` : '';
    if (shape === 'circle') this.add(`<circle${c} cx="${f3(x)}" cy="${f3(y)}" r="${f3(r)}" fill="${fill}"${st}/>`);
    else if (shape === 'square') this.add(`<rect${c} x="${f3(x - r)}" y="${f3(y - r)}" width="${f3(2 * r)}" height="${f3(2 * r)}" fill="${fill}"${st}/>`);
    else if (shape === 'diamond') {
      this.add(`<path${c} d="M ${f3(x)} ${f3(y - r * 1.25)} L ${f3(x + r * 1.25)} ${f3(y)} L ${f3(x)} ${f3(y + r * 1.25)} L ${f3(x - r * 1.25)} ${f3(y)} Z" fill="${fill}"${st}/>`);
    } else if (shape === 'triangle') {
      this.add(`<path${c} d="M ${f3(x)} ${f3(y - r * 1.2)} L ${f3(x + r * 1.15)} ${f3(y + r * 0.85)} L ${f3(x - r * 1.15)} ${f3(y + r * 0.85)} Z" fill="${fill}"${st}/>`);
    } else throw new Error('unknown marker ' + shape);
    return this;
  }
  // Arrow from (x1,y1) to (x2,y2) with a small filled head at the end.
  arrow(x1, y1, x2, y2, { stroke = COLORS.axis, sw = STROKE.arrow, dash = null, head = 2.2, cls = null } = {}) {
    const ang = Math.atan2(y2 - y1, x2 - x1);
    const hx = x2 - head * 0.9 * Math.cos(ang), hy = y2 - head * 0.9 * Math.sin(ang);
    this.line(x1, y1, hx, hy, { stroke, sw, dash, cls });
    const a1 = ang + Math.PI * 0.82, a2 = ang - Math.PI * 0.82;
    const d = `M ${f3(x2)} ${f3(y2)} L ${f3(x2 + head * Math.cos(a1))} ${f3(y2 + head * Math.sin(a1))} L ${f3(x2 + head * Math.cos(a2))} ${f3(y2 + head * Math.sin(a2))} Z`;
    this.path(d, { fill: stroke, cls });
    return this;
  }
  // Standard x axis: bottom spine + ticks + labels (+ optional vertical gridlines).
  xAxis(x0, x1, y, ticks, scale, { title = null, titleDy = 8.5, tickSize = 1.6, grid = null, fmtDp = null, cls = 'axis-x' } = {}) {
    this.line(x0, y, x1, y, { stroke: COLORS.axis, sw: STROKE.axis, cls });
    for (const t of ticks) {
      const x = scale(t);
      if (grid) this.line(x, grid[0], x, y, { stroke: COLORS.grid, sw: STROKE.grid, cls: 'grid' });
      this.line(x, y, x, y + tickSize, { stroke: COLORS.axis, sw: STROKE.axis, cls });
      this.text(x, y + tickSize + SIZE.tick + 0.8, fmtDp == null ? String(t) : fmt(t, fmtDp),
        { size: SIZE.tick, anchor: 'middle', cls: 'tick-label' });
    }
    if (title) this.text((x0 + x1) / 2, y + titleDy + SIZE.axisTitle, title, { size: SIZE.axisTitle, anchor: 'middle', cls: 'axis-title' });
    return this;
  }
  yAxis(x, y0, y1, ticks, scale, { title = null, titleX = null, tickSize = 1.6, grid = null, fmtDp = null, cls = 'axis-y', titleRotate = true } = {}) {
    this.line(x, y0, x, y1, { stroke: COLORS.axis, sw: STROKE.axis, cls });
    for (const t of ticks) {
      const yy = scale(t);
      if (grid) this.line(x, yy, grid, yy, { stroke: COLORS.grid, sw: STROKE.grid, cls: 'grid' });
      this.line(x - tickSize, yy, x, yy, { stroke: COLORS.axis, sw: STROKE.axis, cls });
      this.text(x - tickSize - 1.0, yy + SIZE.tick * 0.36, fmtDp == null ? String(t) : fmt(t, fmtDp),
        { size: SIZE.tick, anchor: 'end', cls: 'tick-label' });
    }
    if (title) {
      const tx = titleX == null ? x - tickSize - 6.2 : titleX;
      if (titleRotate) this.text(tx, (y0 + y1) / 2, title, { size: SIZE.axisTitle, anchor: 'middle', rotate: -90, cls: 'axis-title' });
      else this.text(tx, (y0 + y1) / 2, title, { size: SIZE.axisTitle, cls: 'axis-title' });
    }
    return this;
  }
  panelLetter(x, y, letter) {
    this.text(x, y, letter, { size: SIZE.panelLetter, weight: 'bold', cls: 'panel-letter' });
    return this;
  }
  panelTitle(x, y, title) {
    this.text(x, y, title, { size: SIZE.panelTitle, weight: 'bold', cls: 'panel-title' });
    return this;
  }
  legendItem(x, y, { shape = null, color, label, dash = null, lineSw = null }, sizeMm = SIZE.legend) {
    if (shape) this.marker(x, y - sizeMm * 0.32, shape, sizeMm * 0.55, color);
    else this.line(x - 2.2, y - sizeMm * 0.32, x + 2.2, y - sizeMm * 0.32,
      { stroke: color, sw: lineSw || STROKE.connector * 1.6, dash });
    this.text(x + 3.2, y, label, { size: sizeMm, cls: 'legend-label' });
    return x + 3.2 + textWidth(label, sizeMm) + 5.5; // next x
  }
  render() {
    return `<?xml version="1.0" encoding="UTF-8"?>\n` +
      `<svg xmlns="http://www.w3.org/2000/svg" width="${this.w}mm" height="${this.h}mm" viewBox="0 0 ${this.w} ${this.h}">\n` +
      `<rect x="0" y="0" width="${this.w}" height="${this.h}" fill="#FFFFFF"/>\n` +
      (this.defs.length ? `<defs>${this.defs.join('')}</defs>\n` : '') +
      this.parts.join('\n') + '\n</svg>\n';
  }
}

export function f3(v) {
  const s = Number(v).toFixed(3);
  return s.replace(/\.?0+$/, '') || '0';
}

// Heatmap helper: sequential blue scale (perceptually smooth, print-safe).
// t in [0,1] -> light to dark blue. Text color chosen by threshold.
export function heatColor(t) {
  const stops = [
    [0.00, [247, 250, 252]], [0.25, [222, 235, 244]], [0.50, [158, 197, 225]],
    [0.75, [63, 132, 188]], [1.00, [8, 81, 145]],
  ];
  for (let i = 1; i < stops.length; i++) {
    if (t <= stops[i][0]) {
      const [t0, c0] = stops[i - 1], [t1, c1] = stops[i];
      const k = (t - t0) / (t1 - t0);
      const c = c0.map((v, j) => Math.round(v + (c1[j] - v) * k));
      return `rgb(${c[0]},${c[1]},${c[2]})`;
    }
  }
  return 'rgb(8,81,145)';
}
export function heatTextColor(t) { return t > 0.55 ? '#FFFFFF' : '#1A1D21'; }

// Neutral sequential orange scale for the predicted-NA heatmap (S3a).
export function heatColorOrange(t) {
  const stops = [
    [0.00, [255, 250, 244]], [0.25, [253, 230, 205]], [0.50, [246, 190, 132]],
    [0.75, [222, 122, 47]], [1.00, [166, 70, 12]],
  ];
  for (let i = 1; i < stops.length; i++) {
    if (t <= stops[i][0]) {
      const [t0, c0] = stops[i - 1], [t1, c1] = stops[i];
      const k = (t - t0) / (t1 - t0);
      const c = c0.map((v, j) => Math.round(v + (c1[j] - v) * k));
      return `rgb(${c[0]},${c[1]},${c[2]})`;
    }
  }
  return 'rgb(166,70,12)';
}
export function heatTextColorOrange(t) { return t > 0.62 ? '#FFFFFF' : '#1A1D21'; }
