import json
from pathlib import Path


roots = [Path("/content/clef-output")]
files = []
for root in roots:
    if not root.exists():
        continue
    candidates = [root / "run-result.json", root / "download-progress.jsonl"]
    raw_dir = root / "raw"
    if raw_dir.exists():
        candidates.extend(sorted(raw_dir.rglob("*")))
    for path in candidates:
        if path.is_file():
            files.append(
                {
                    "path": str(path),
                    "bytes": path.stat().st_size,
                    "content": path.read_text(encoding="utf-8"),
                }
            )

print("REMOTE_EVIDENCE_CAPTURE_BEGIN", flush=True)
print(json.dumps({"files": files}, ensure_ascii=False, separators=(",", ":")), flush=True)
print("REMOTE_EVIDENCE_CAPTURE_END", flush=True)
