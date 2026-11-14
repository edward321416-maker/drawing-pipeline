# C-T14L | Codex V4.3 integration instructions (NOT FROZEN)

Repo edward321416-maker/drawing-pipeline; base Draft PR #19 at aa8217a34c18e45075df5fd344de2d5d8a4baac9; this work is PR #20 Draft only.

1. Use an isolated worktree: D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14L. Preserve main, original V4.2, PR #19, A-003, 1F_master.blend, model_world.npz, original render and model caches. Do not merge, force-push, freeze, purchase paid API or invent architecture.
2. Read repository project rules and exact current PR branches. Inspect code signatures first. Parse package/requirements manifests as metadata, do not run them. Record actual HEAD, sources and hashes.
3. Enumerate all graphics in Part I 16 pages and Part II 49 pages (text-only pages exempt): ID, kind, source hash, source model, printed size, protected vector, image prompt, download proof, result hash, independent review, final composite and PDF crop.
4. PILOT G-002 only: verify source JPEG bytes/hash; submit real JPG + structural locks to ChatGPT or Adobe. Actually download edited PNG and log original/edit hashes plus export reference. If tool cannot accept the image, mark AWAITING_EXTERNAL_AI_RETOUCH, do not claim an edit happened.
5. Prepare before/after full-page and crops at roof, cores, tubes, floors, voids, garden and base; review silhouette, camera and building geometry separately. The geometry checklist requires a real independent reviewer. Automated matching cannot prove design truth.
6. Run: python tools/t14l/retouch_gate.py <manifest.json> --report <candidate_qa.json>. Do not insert unapproved outputs.
7. To pass print gate run with --print-gate and record actual printed width and PDF page render inspection. G-002 at existing 396mm is about 154dpi, so require a native same-camera Blender rerender near 4700×2640 or change placement. AI fake detail does not solve resolution.
8. Then extend to G-103, G-106 and G-111 sequentially. Technical plans/elevations/sections/details use AI only as background; original verified linework/dimensions/text/scalebar are recomposed on top. Compare final composite to pixel-exact composition and retain true vector PDF as authority.
9. Rebuild a separate Candidate V4.3 only from passed assets and run complete printed-page, 200dpi/300dpi, text collision, panel trim and source hash QA. Do not silently substitute old assets with unverified edited ones. If actual editing is blocked, preserve V4.2 and report blocker.
10. Deliver original/edited/checklist/comparison/QA manifest and PDF page renders together with an independently reviewed human-readable PDF report and a Draft PR. Do not announce V4.3 until real outputs exist.

Gate states: AWAITING_EXTERNAL_AI_RETOUCH, REJECTED_NOT_FOR_BOOK, APPROVED_FOR_LAYOUT_NOT_DESIGN_APPROVED, APPROVED_FOR_PRINT_NOT_DESIGN_APPROVED. Neither approval implies architectural or structural final approval.

Codex model recommendation: GPT-6 High for inventory and implementation; GPT-6 Extra High for model/geometry risk and final PR review if available. Record actual model used and avoid fabricated model/tool execution claims.
