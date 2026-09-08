// Frozen visual system for the AEG/GEJ submission figures.
// Single source of truth for colors, typography, and marker mapping.
// Keep visual-system changes explicit and reviewable in source control.

export const PT = 0.3527778; // mm per pt

export const COLORS = {
  blue: '#0072B2',      // macro-F1 / primary
  teal: '#009E73',      // evidence coverage / PASS / Yes-sufficient
  orange: '#E69F00',    // micro-F1 / Partial
  vermillion: '#D55E00',// all-snippet recoverability / FAIL / No-insufficient
  purple: '#7A5AF8',    // conditional item recoverability
  darkGrey: '#5F6670',  // Regex (deterministic baseline)
  midGrey: '#B8C0CC',   // NA
  faintGrey: '#EEF1F4', // fills / separators
  axis: '#3A3F44',
  grid: '#E3E7EC',
  text: '#1A1D21',
  subtext: '#4A5058',
};

export const FONT = 'Arial, Helvetica, sans-serif';

export const SIZE = {
  label: 7 * PT,       // ordinary labels (mm)
  tick: 7 * PT,
  panelTitle: 8.5 * PT,
  panelLetter: 9 * PT,
  axisTitle: 7.5 * PT,
  legend: 7 * PT,
};

// Fixed metric encodings (color + shape). Never reuse these pairs for other metrics.
export const METRIC_STYLE = {
  macroF1:     { color: COLORS.blue,       shape: 'circle',  label: 'Macro-F1' },
  microF1:     { color: COLORS.orange,     shape: 'square',  label: 'Micro-F1' },
  coverage:    { color: COLORS.teal,       shape: 'circle',  label: 'Evidence coverage' },
  conditional: { color: COLORS.purple,     shape: 'diamond', label: 'Conditional item recoverability' },
  allSnippet:  { color: COLORS.vermillion, shape: 'square',  label: 'All-snippet recoverability' },
  regex:       { color: COLORS.darkGrey,   shape: 'circle',  label: 'Regex (deterministic baseline)' },
};

export const VERDICT_STYLE = {
  PASS: { color: COLORS.teal,       label: 'PASS' },
  FAIL: { color: COLORS.vermillion, label: 'FAIL' },
  NA:   { color: COLORS.midGrey,    label: 'NA' },
};

export const REVIEW_STYLE = {
  yes:     { color: COLORS.teal,       label: 'Yes / sufficient' },
  partial: { color: COLORS.orange,     label: 'Partial' },
  no:      { color: COLORS.vermillion, label: 'No / insufficient' },
};

export const STROKE = {
  axis: 1 * PT,
  errorbar: 1 * PT,
  connector: 0.75 * PT,
  grid: 0.5 * PT,
  node: 1 * PT,
  arrow: 1.25 * PT,
};

// Model display order is data-driven (canonical_model_order.json); Regex is always last.
export function isRegex(displayName) { return displayName === 'Regex'; }
