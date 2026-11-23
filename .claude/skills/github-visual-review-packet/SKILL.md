---
name: github-visual-review-packet
description: Use when drawings or renders are handed to an independent reviewer through GitHub and the reviewer must inspect real pixels, when a PNG is too large for the GitHub connector, or after a push to confirm the packet on the remote is byte-identical to the local one.
metadata:
  status: CANDIDATE_UNREVIEWED
  version: 0.1.0
---

# github-visual-review-packet

Builds and checks GitHub-readable packets: JPEG previews, native-resolution lossless PNG tiles, manifest, README. Status: **candidate, not independently reviewed.**

## Trigger
- Any handoff of new or changed drawings (policy: repository `AGENTS.md` section 10, `docs/t14r_visual_review/POLICY_KO.md`).
- After pushing a packet: remote verification.

Not for: approving a drawing. The checks cover bytes and pixels only.

## Inputs
Source images (absolute paths, one `LABEL=path` each; labels match `^[A-Za-z][A-Za-z0-9_-]{0,63}$`), an output folder under `docs/<task>/review_packet`, the pushed commit SHA.

## Procedure
1. Pack with the project tool (do not reimplement): `python -I tools/t14r/export_visual_review.py pack --out docs/<task>/review_packet --asset FLOOR_3F=<abs path to png> ...`. The default budget is 400 KiB per file. The tool refuses to overwrite an existing tile.
2. `python -I ${CLAUDE_SKILL_DIR}/scripts/packet_check.py local --packet docs/<task>/review_packet --root .` runs T14R `verify` plus: no unlisted files, nothing over budget, README present, readback status.
3. Commit and push to the task's Draft PR branch (see `references/packet_protocol.md` for the byte-exactness setting on Windows).
4. `python -I ${CLAUDE_SKILL_DIR}/scripts/packet_check.py remote --packet docs/<task>/review_packet --repo OWNER/REPO --ref <pushed SHA> --root .` compares every packet file's git blob SHA with the remote tree and downloads an even sample raw.
5. Before/after previews and the Korean A3 PDF are made by the task's packaging script (example: `tools/t14s/package_t14t.py`). Give each corrected drawing one before/after pair.

## Outputs
Packet folder, `PASS_BYTES_AND_PIXELS_ONLY` from `local`, `REMOTE_BYTE_IDENTITY_PASS` from `remote`.

## Example
```
python -I ${CLAUDE_SKILL_DIR}/scripts/packet_check.py local --packet docs/t14t_corrections/review_packet --root .
{"check": "local", "ok": true, "assets": 16, "tiles": 256, "github_readback": "NOT_TESTED", ...}
```

## Safety boundaries
- `github_readback` stays `NOT_TESTED` until a reviewer's real readback produces `readback_report.json` with `tested_by` and `files_decoded`. Never write that file yourself and never say a connector readback passed without it.
- `REMOTE_BYTE_IDENTITY_PASS` means GitHub holds identical bytes. It does not mean the reviewer's connector can decode them. Empty content or a read failure is `GITHUB_PUSHED_UNREADABLE`: resubmit smaller tiles.
- Never modify source masters. Never push to a base or earlier PR branch. Visual and architectural approval stay `INDEPENDENT_VISUAL_REVIEW_PENDING`.

## Tests
`pytest tests/test_claude_skills.py -k packet` (valid packet, corrupt tile, unlisted file; remote match, mismatch, empty download).
