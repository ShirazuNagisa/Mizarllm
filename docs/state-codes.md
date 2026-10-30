# State codes

AGI Mizar draws a session's status from a one-byte code. The full table lives in the app
(`agi-protocol::SessionState`, generated from the workspace's `protocol/states.json`); this model only
ever produces four of them, and `manifest.json` is what performs the mapping.

| Verdict | Code | State | When |
|---|---:|---|---|
| `done` | 11 | Completed | the user's instruction was carried out or answered |
| `needs_user` | 4 | AwaitingUser | the turn stops and asks the user something |
| `stalled` | 9 | Failed | the turn ended without either of the above |
| `waiting` | 8 | Background | still running (subagent / background task), asked before the model is |

Codes 0–15 exist; the model never emits `thinking` (1), `tool` (2), `awaiting_approval` (3),
`stream_narration` (5), `stream_final` (6), `subagent` (7), `editing` (10), `paused` (12),
`compacting` (13), `retrying` (14) or `queued` (15). Those come from the record stream, not from a
judgement — the app derives them structurally and never asks a model.

## Why the model is asked at all

Structure is cheap and reliable: a `turn/end` with reason `error` is `failed`; a live subagent is
`background`; an open approval is `awaiting_approval`. None of those need a model, and the app gates them
before it spends a round trip.

What structure cannot answer is whether the work **answered the instruction**. An agent can finish
cleanly, produce a long tidy summary, and still leave the request half done — or stop mid-way and ask a
question in prose. That is the only question this model exists to answer.

## Output contract

The sidecar is `llama-server`; one judgement is a `/completion` call with `n_predict: 24` and a prompt
built from the turn's fact sheet. The first parseable token `{"state":"done"}` wins. Anything else —
timeout, malformed JSON, an unknown state — falls back to the structural rules, and the app records the
verdict's source as `rule` rather than `model`. A silent downgrade is a bug in the client, so the app
surfaces it in its settings page instead of pretending the model decided.

## Tuning note

`stalled` recall is deliberately the weakest number (65%). A false "did not finish" is the one error a
user cannot verify from the transcript, so the model under-claims it; `done` and `needs_user` carry the
accuracy instead.
