#!/usr/bin/env python3
"""Publish one release of the judge model to ModelScope.

Why this exists: the GitHub release CDN answers around 10 KB/s from mainland
China and ModelScope answered ~13 MiB/s from the same machine, so AGI Mizar tries
ModelScope first and GitHub second
(see `docs/desktop/agi-mizar-model-download-acceleration-2026-11-12.md`).

Two rules the order encodes:

- the weights upload **before** `manifest.json`, so a client that reads the
  manifest in between never finds it naming a file the mirror does not have;
- nothing is uploaded until the file's sha256 matches the manifest, because a
  mirror serving different bytes under the same version is worse than no mirror.

Usage:

    pip install modelscope            # once
    export MODELSCOPE_API_TOKEN=...   # https://modelscope.cn/my/myaccesstoken
    python tools/publish-modelscope.py --gguf ../models/mizarllm-v1-q4km.gguf --push

Without `--push` it only stages and verifies, which is the useful review step.
A model repository that does not exist yet is created public (Apache-2.0).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
MODEL_ID = "Sh1razu/Mizarllm"
# The file git cannot hold is also the one the app streams: keep the set small
# and the names the same as the GitHub release.
EXTRAS = ["SHA256SUMS", "LICENSE", "NOTICE", "LICENSES"]


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_of(root: Path) -> dict:
    return json.loads((root / "manifest.json").read_text(encoding="utf-8"))


def find_gguf(root: Path, name: str, given: str | None) -> Path:
    if given:
        path = Path(given).expanduser()
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        return path
    # The workspace keeps the weights beside this repository, under the release
    # name or the short local name.
    for candidate in (root / "release" / name, root.parent / "models" / name,
                      root.parent / "models" / "mizarllm-v1-q4km.gguf"):
        if candidate.is_file():
            return candidate
    raise SystemExit(
        f"cannot find {name}; pass --gguf <path> (the weights are not in git)"
    )


def stage(work: Path, manifest: dict, gguf: Path) -> Path:
    """Collect exactly what the mirror should hold, weights last to be linked."""
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    card = f"""# Mizarllm

The judge model AGI Mizar runs locally: given one coding-agent turn, decide
whether the user's instruction is `done`, `needs_user`, `stalled` or `waiting`.

- Base: Qwen/Qwen3-1.7B (Apache-2.0), LoRA fine-tune, merged and quantised to
  Q4_K_M (~1.0 GiB).
- Release `{manifest['version']}`: `{manifest['file']}`, sha256
  `{manifest['sha256']}`.
- This repository is a mirror of the GitHub release. Source, issues and the
  release notes live at https://github.com/ShirazuNagisa/Mizarllm

AGI Mizar downloads `manifest.json` and then the weights from here, and checks
the sha256 before the model is used.
"""
    (work / "README.md").write_text(card, encoding="utf-8")
    for name in EXTRAS:
        source = ROOT / name
        if source.is_dir():
            shutil.copytree(source, work / name)
        elif source.is_file():
            shutil.copy2(source, work / name)
    (work / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    # Hard link: a 1 GB copy per publish is space nobody gets back, and the two
    # names are never written through after this point.
    try:
        os.link(gguf, work / manifest["file"])
    except OSError:
        shutil.copy2(gguf, work / manifest["file"])
    return work


def repo_exists() -> bool:
    """Whether the model repository already answers publicly.

    Anonymous on purpose: a repository the client cannot read is one this script
    cannot publish to either, and a 404 here means "create it" rather than "the
    token is wrong".
    """
    try:
        with urlopen(f"https://modelscope.cn/api/v1/models/{MODEL_ID}", timeout=10) as response:
            return response.status == 200
    except Exception:  # noqa: BLE001 - any failure means "not there yet"
        return False


def upload(work: Path, manifest: dict, token: str | None) -> None:
    try:
        from modelscope.hub.api import HubApi
    except ImportError:
        raise SystemExit(
            "the modelscope package is not installed: pip install modelscope"
        )

    api = HubApi()

    def auth() -> str | None:
        # The SDK reads MODELSCOPE_API_TOKEN itself; passing it explicitly keeps
        # the failure obvious when neither is set.
        if token:
            api.login(token)
        return token

    token = auth()

    # The repository usually exists already (it is created in the web UI before
    # the first upload), and `create_model` answers with an error string in the
    # server's language. Ask the public API first: it is one request and it makes
    # the common case not depend on parsing an error.
    if repo_exists():
        print(f"{MODEL_ID} already exists")
    else:
        try:
            api.create_model(
                model_id=MODEL_ID, license="Apache License 2.0", token=token
            )
            print(f"created {MODEL_ID}")
        except Exception as error:  # noqa: BLE001 - an exists error is not a failure
            text = str(error).lower()
            if not any(word in text for word in ("exist", "已存在", "409")):
                raise
            print(f"{MODEL_ID} already exists")

    # Weights first, manifest last: the order is the whole point. Everything
    # else sits between them, once each.
    names = [entry.name for entry in work.iterdir() if entry.name != "manifest.json"]
    rest = sorted(name for name in names if name != manifest["file"])
    steps = [manifest["file"], *rest, "manifest.json"]
    for index, name in enumerate(steps, start=1):
        path = work / name
        if not path.is_file():
            # Directories (LICENSES) are uploaded file by file.
            for nested in sorted(path.rglob("*")):
                if nested.is_file():
                    api.upload_file(
                        path_or_fileobj=str(nested),
                        path_in_repo=str(nested.relative_to(work)),
                        repo_id=MODEL_ID,
                        token=token,
                        commit_message=f"Mizarllm {manifest['version']}",
                    )
            continue
        size = path.stat().st_size
        print(f"[{index}/{len(steps)}] {name} ({size / 1048576:.1f} MiB)")
        api.upload_file(
            path_or_fileobj=str(path),
            path_in_repo=name,
            repo_id=MODEL_ID,
            token=token,
            commit_message=f"Mizarllm {manifest['version']}: {name}",
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gguf", help="the weights to publish (default: find them)")
    parser.add_argument("--work", default=str(ROOT / ".modelscope-work" / "stage"))
    parser.add_argument("--push", action="store_true", help="upload; without it, only verify")
    args = parser.parse_args()

    manifest = manifest_of(ROOT)
    for field in ("version", "file", "sha256"):
        if not manifest.get(field):
            raise SystemExit(f"manifest.json has no {field}; refusing to publish")
    print(f"release {manifest['version']} · {manifest['file']}")

    gguf = find_gguf(ROOT, manifest["file"], args.gguf)
    if not gguf.is_file():
        raise SystemExit(f"no weights at {gguf}")
    actual = sha256_of(gguf)
    if actual != manifest["sha256"]:
        raise SystemExit(
            f"checksum mismatch: manifest says {manifest['sha256']}, {gguf} is {actual}"
        )
    print(f"checksum ok ({actual})")

    work = stage(Path(args.work), manifest, gguf)
    print(f"staged {work}")

    if not args.push:
        print("dry run: nothing uploaded. Re-run with --push to publish.")
        return 0

    token = os.environ.get("MODELSCOPE_API_TOKEN") or None
    if token is None:
        # The SDK keeps its own login, so a machine that ran `modelscope login`
        # still works; say so instead of demanding the variable.
        print("MODELSCOPE_API_TOKEN is not set; relying on an existing `modelscope login`")
    upload(work, manifest, token)

    print("\npublished. These two must answer, the weights before the manifest:")
    print(f"  https://modelscope.cn/models/{MODEL_ID}/resolve/master/{manifest['file']}")
    print(f"  https://modelscope.cn/models/{MODEL_ID}/resolve/master/manifest.json")
    print(f"and the manifest's sha256 must equal {manifest['sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
