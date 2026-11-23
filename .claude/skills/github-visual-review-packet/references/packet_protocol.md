# Packet protocol notes (from C-T14R, C-T14S, C-T14T)

## Why tiles
GitHub connectors can return empty content for files of about 20 MB. Each preview and tile is kept at or below 400 KiB, tiles are lossless PNG at native pixel coordinates (800 px squares in the C-T14T packet), previews are JPEG. `manifest.json` carries the source SHA256, pixel SHA256, tile bounds and file SHAs, so `verify` can rebuild the image from tiles and compare pixels.

## Checklist
1. Source image exists and is untouched (hash recorded in the manifest as `original_sha256`).
2. `pack`, then `packet_check.py local`.
3. Windows byte-exactness: add `-text` for the deliverable and packet folders to `.gitattributes` before the first commit (example lines in the repository `.gitattributes` for `outputs/T14T/**` and `docs/t14t_corrections/review_packet/**`). Otherwise line-ending conversion changes bytes and the SHA manifest no longer matches what GitHub holds.
4. Push to the task's own Draft PR branch. Set no upstream to the base branch (`git branch --unset-upstream` after `git worktree add ... origin/<base>`).
5. `packet_check.py remote` with the pushed commit SHA.
6. State in the handoff: `local` result, `remote` result, `github_readback: NOT_TESTED` unless a reviewer reported otherwise.

## Per-drawing handoff items
- Revised preview and lossless tiles (packet).
- Before/after preview per corrected drawing, with the correction reason in words.
- Concise A3 landscape PDF with corrected previews and unresolved decision items.
- Metadata and SHA256 manifests.
- Full absolute local paths in code format when reporting to the user (repository `AGENTS.md` section 0).

## Known limits
- `verify_packet` proves tile coverage and pixel equality only.
- The remote check samples raw downloads (default 6 files). Blob SHAs cover every file.
- A tree larger than the GitHub API limit is reported as truncated and fails the check.
