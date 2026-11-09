# Mizarllm

A 1.7B model that answers one question about a coding-agent turn: **is the user's instruction finished,
waiting on them, still running, or stalled?**

AGI Mizar already knows the structure of a turn — which tools ran, whether a subagent is still alive,
how it ended. What structure cannot tell you is whether the work actually answered what was asked. That
judgement is this model's whole job. Everything else stays a rule (see [`docs/state-codes.md`](docs/state-codes.md)).

- Base: [`Qwen/Qwen3-1.7B`](https://huggingface.co/Qwen/Qwen3-1.7B) (Apache-2.0), LoRA fine-tune, merged and
  quantised to Q4_K_M (~1.0 GiB).
- Holdout: **87.8%** four-way accuracy; **stalled recall 65%** (a wrong "did not finish" is the one error a
  user cannot verify, so the model is tuned to under-claim it).
- Input: a compact fact sheet per turn (user instruction, tools used, ending reason, reply text).
- Output: one of `done` / `needs_user` / `stalled` / `waiting`, mapped onto AGI Mizar's state codes by
  [`manifest.json`](manifest.json) — not by the kernel.

## Use it

The weights are **not** in this repository (GitHub caps files at 100 MB). They ship as release assets
under the `v1` tag (model file 1.0.0):

```sh
gh release download v1 --repo ShirazuNagisa/Mizarllm \
  --pattern '*.gguf' --pattern 'SHA256SUMS'   # or download by hand
sha256sum -c SHA256SUMS
```

Then serve it with `llama-server` (from [llama.cpp](https://github.com/ggml-org/llama.cpp)):

```sh
llama-server -m mizarllm-1.0.0-q4km.gguf --port 8791 --ctx-size 4096 -t 4
```

and point AGI Mizar at it (`MIZAR_LAYOUT_URL=http://127.0.0.1:8791`), or install the app and let its
onboarding fetch the model and start the server for you.

One judgement is a single `/completion` round trip with `n_predict: 24`; the model stays warm in the
sidecar, so a verdict costs tens of milliseconds, not a process spawn.

## This repository

```
manifest.json          # id, version, backend, and the four labels → state codes
tools/export_gguf.py   # merge the LoRA adapter into Qwen3-1.7B and quantise
tools/gen-manifest.py  # write manifest.json + SHA256SUMS for a built GGUF
docs/state-codes.md    # the twelve-plus states and which four verdicts reach them
```

## License

The fine-tune and this repository are Apache-2.0. The base model is Qwen3-1.7B, also Apache-2.0; its
license is reproduced in [`LICENSES/Qwen3-1.7B.txt`](LICENSES/Qwen3-1.7B.txt) and attribution is in
[`NOTICE`](NOTICE).

The training data is derived from the operator's own agent sessions and is **not** redistributed here.
