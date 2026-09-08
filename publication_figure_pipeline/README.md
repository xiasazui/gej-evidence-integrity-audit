# Canonical publication-figure pipeline

This directory is the exact source for the locked three main figures and five composite supplementary figures. It contains no real or real-derived case text; all inputs are frozen aggregate CSV/JSON tables.

## Regenerate SVGs

```bash
cd source/figure_sources
python3 build_canonical.py
node fig1.mjs && node fig2.mjs && node fig3.mjs
node figS1.mjs && node figS2.mjs && node figS3.mjs && node figS4.mjs && node figS5.mjs
```

The scripts write SVGs to `main_figures/` and `supplementary_figures/`.

## Render PDF and 600 dpi PNG

`render.mjs` requires Node.js 18 or newer, Google Chrome, Python 3, and PyMuPDF. Example:

```bash
node render.mjs ../../main_figures/Figure_1.svg ../../main_figures/Figure_1.pdf \
  ../../main_figures/Figure_1_600dpi.png 180 68
```

Exact dimensions in millimetres are:

- Figure 1: 180 × 68
- Figure 2: 180 × 97
- Figure 3: 180 × 78
- Supplementary Figure S1: 170 × 63
- Supplementary Figure S2: 170 × 119
- Supplementary Figure S3: 170 × 121
- Supplementary Figure S4: 170 × 136
- Supplementary Figure S5: 170 × 112

The journal-facing files in `../figures/` are copies of these locked outputs. Supplementary files there use descriptive names; the panel content is unchanged.
