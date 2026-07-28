from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {"release_manifest.json", "MANIFEST.sha256"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    existing = json.loads((ROOT / "release_manifest.json").read_text(encoding="utf-8"))
    files = []
    for path in sorted(path for path in ROOT.rglob("*") if path.is_file() and path.name not in EXCLUDED):
        files.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )

    manifest = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": "PRIVATE_REMOTE_STAGING_PUBLICATION_DEFERRED_UNTIL_SUBMISSION",
        "title": existing["title"],
        "source_package_manifest_sha256": existing["source_package_manifest_sha256"],
        "source_canonical_gold_sha256": existing["source_canonical_gold_sha256"],
        "institutional_synthetic_scope_confirmed": True,
        "remote_repository_visibility": "PRIVATE",
        "private_remote_staging_authorized": True,
        "remote_publication_deferred_until_submission": True,
        "synthetic_provenance_label": "script-generated synthetic records",
        "public_scope": "80 synthetic originals, 480 synthetic-derived variants, synthetic-only record-level artifacts, aggregate data, code and figures",
        "restricted_scope": "20 real originals, 120 real-derived variants, all real-source record-level artifacts and Appendix B",
        "synthetic_originals": 80,
        "synthetic_derived": 480,
        "synthetic_cases": 560,
        "systems": 11,
        "consolidated_output_files": 11,
        "frozen_output_records": 6160,
        "released_case_name_normalization": "synthetic name replaced by package-local patient identifier",
        "licensing": existing["licensing"],
        "files": files,
    }
    manifest_path = ROOT / "release_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    manifest_lines = [f'{row["sha256"]}  {row["path"]}\n' for row in files]
    manifest_lines.append(f"{sha256(manifest_path)}  release_manifest.json\n")
    (ROOT / "MANIFEST.sha256").write_text("".join(manifest_lines), encoding="utf-8")
    print(f"refreshed {len(files)} manifested files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
