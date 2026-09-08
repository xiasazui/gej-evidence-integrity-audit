// render.mjs — deterministic SVG -> vector PDF (headless Chrome) -> 600 dpi PNG (PyMuPDF).
// Usage: node render.mjs <svgPath> <pdfPath> <pngPath> <widthMm> <heightMm>
// Chrome headless does not reliably exit after print-to-pdf, so we spawn it,
// poll until the PDF is fully written (size stable), then terminate Chrome.
import { readFileSync, writeFileSync, statSync, existsSync, rmSync } from 'node:fs';
import { spawn, execFileSync } from 'node:child_process';
import { dirname, resolve } from 'node:path';

const [svgPath, pdfPath, pngPath, wMm, hMm] = process.argv.slice(2);
if (!svgPath || !pdfPath || !pngPath || !wMm || !hMm) {
  console.error('usage: node render.mjs <svg> <pdf> <png> <wMm> <hMm>');
  process.exit(1);
}
const svg = readFileSync(svgPath, 'utf8');
const svgBody = svg.replace(/^<\?xml[^?]*\?>\s*/, '');
const html = `<!doctype html><html><head><meta charset="utf-8"><style>
@page { size: ${wMm}mm ${hMm}mm; margin: 0; }
html, body { margin: 0; padding: 0; }
svg { display: block; }
</style></head><body>${svgBody}</body></html>`;
const tmpHtml = `/tmp/aeg_render_${process.pid}.html`;
writeFileSync(tmpHtml, html);

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const profile = `/tmp/aeg_chrome_profile_${process.pid}`;
const pdfAbs = resolve(pdfPath);
if (existsSync(pdfAbs)) rmSync(pdfAbs);

const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--no-pdf-header-footer',
  `--user-data-dir=${profile}`, '--no-first-run', '--no-default-browser-check',
  '--disable-background-networking', '--disable-sync', '--disable-component-update',
  '--disable-extensions', '--metrics-recording-only', '--mute-audio',
  `--print-to-pdf=${pdfAbs}`, `file://${tmpHtml}`], { stdio: 'ignore' });

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function waitForPdf() {
  let lastSize = -1, stable = 0;
  const deadline = Date.now() + 90000;
  while (Date.now() < deadline) {
    if (existsSync(pdfAbs)) {
      const s = statSync(pdfAbs).size;
      if (s > 0 && s === lastSize) {
        stable += 1;
        if (stable >= 3) return true;   // size stable across ~900 ms
      } else stable = 0;
      lastSize = s;
    }
    await sleep(300);
  }
  return false;
}

const ok = await waitForPdf();
try { chrome.kill('SIGKILL'); } catch {}
rmSync(tmpHtml, { force: true });
rmSync(profile, { recursive: true, force: true });
if (!ok) { console.error('ERROR: PDF not produced within timeout'); process.exit(1); }

// PNG at 600 dpi + structural checks via PyMuPDF
const python = process.env.AEG_PYTHON || 'python3';
const out = execFileSync(python, ['-c', `
import fitz, json
doc = fitz.open(${JSON.stringify(pdfAbs)})
p = doc[0]
info = {
  "pages": doc.page_count,
  "width_mm": round(p.rect.width / 72 * 25.4, 2),
  "height_mm": round(p.rect.height / 72 * 25.4, 2),
  "images": len(p.get_images()),
  "text_chars": len(p.get_text().strip()),
}
pix = p.get_pixmap(dpi=600)
pix.save(${JSON.stringify(resolve(pngPath))})
info["png_px"] = [pix.width, pix.height]
print(json.dumps(info))
`], { encoding: 'utf8' });
console.log(out.trim());
