#!/usr/bin/env python3
"""Write `manifest.json` and `SHA256SUMS` for a built GGUF.

    python tools/gen-manifest.py --gguf build/mizarllm-1.0.0-q4km.gguf --version 1.0.0

The manifest is what AGI Mizar reads to decide *what* this model is: its id, its
version, the four labels it answers with, and the endpoint its host will inject.
Everything here is derived except the labels and the note — those are judgement
calls about the model, so they live in `LABELS` and are edited by hand when a
retrain changes what a verdict means.
"""
import argparse
import hashlib
import json
import os
import sys

# Four verdicts → AGI Mizar state codes. Keep in sync with the app's
# `agi-protocol::SessionState`: 11 completed, 4 awaiting_user, 9 failed, 8 background.
LABELS = {"done": 11, "needs_user": 4, "stalled": 9, "waiting": 8}

NOTE = (
    "Qwen3-1.7B + LoRA, Q4_K_M. 87.8% on holdout; stalled recall 65%. "
    "Four verdicts mapped onto state codes by this file, not by the kernel. "
    "endpoint port 0 means the host picks one and injects it."
)


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--id", default="mizarllm-v1")
    ap.add_argument("--out", default=".")
    args = ap.parse_args()

    if not os.path.exists(args.gguf):
        print(f"!! no such file: {args.gguf}", file=sys.stderr)
        return 1

    name = os.path.basename(args.gguf)
    digest = sha256(args.gguf)
    size = os.path.getsize(args.gguf)

    manifest = {
        "id": args.id,
        "version": args.version,
        "backend": {"kind": "http", "endpoint": "http://127.0.0.1:0", "timeout_ms": 1500},
        "labels": LABELS,
        "note": NOTE,
        "file": name,
        "sha256": digest,
        "size_bytes": size,
    }

    with open(os.path.join(args.out, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)
        fh.write("\n")
    with open(os.path.join(args.out, "SHA256SUMS"), "w") as fh:
        fh.write(f"{digest}  {name}\n")

    print(f"== {name}: {size:,} bytes, sha256 {digest[:16]}…")
    print("== wrote manifest.json and SHA256SUMS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
