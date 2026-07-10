# BUILD-LESSONS-LEDGER.md — image-plane (LEE-411) repo-local standing lessons

DRAFT — staged 2026-07-10, becomes canonical on Lee's ratification. Repo-local lessons
(IP-Lnn), each born from a real incident. Cross-repo lessons live in
`~/processpnlv2/docs/BUILD-LESSONS-LEDGER.md`.

- **IP-L1 — counts come from the join, never a row count.** allocation_v2's row count was
  quoted as "allocated" while containing excluded/no-ref/non-keep rows (5,200-vs-5,775
  incident, 10 Jul). Guard: `counts.py` is the ONLY quotable source; flags file marks the
  misreadable rows; receipt gate demands same-turn `Counted by:`.
- **IP-L2 — "no evidence" requires the FULL source process.** An agent declared 413 jobs
  no-evidence from folder names + invoice text while known_entities (151 refs), Gmail
  (local mbox) and Drive doc contents went unchecked; Lee had to intervene (10 Jul, Ask
  Ledger). Guard: address-stores inventory doc + skill hard rule; half-search rule (looked
  in / could not look in) on every missing/dead claim.
- **IP-L3 — a Lee surface must say what Lee should DO.** Sheets shipped asking "which roof?"
  with no how-to-answer; Lee opened cold and bounced (10 Jul, Ask Ledger). Guard:
  how-to-answer blocks live in the sheet builder headers; "does Lee know what to do next"
  is part of the operator pass.
- **IP-L4 — never match a Drive folder on bare ref.** 18 refs collide across the 4 Drive
  trees (same NNNN-YY, different sites). Guard: `grind/drive_folder_index.json` keys
  ref+tree; never commit it (client names).
- **IP-L5 — Takeout re-encodes: the two photo ledgers can NEVER be hash-deduped.** sha256
  overlap = 0 across 5,054 takeout rows by construction, not by accident. Basename overlap
  (~1.2k) is the only weak key. Do not rebuild hash-dedup attempts.
- **IP-L6 — pin PYTHONHASHSEED on anything that clusters/iterates sets of paths.**
  f2_residual_clusters_v3.py produced 296/297/298 clusters on identical data (string-hash
  randomisation). Owed fix: sort before clustering. Until then: PYTHONHASHSEED=0.
- **IP-L7 — tests must be hermetic w.r.t. Lee-queue files.** tests_guards.py wrote a fake
  species into Lee's real exemplar queue every run (caught 10 Jul). Guard: temp-path
  redirection inside the test, restore in finally.
- **IP-L8 — date is REQUIRED on every allocation row.** 84 rows landed dateless (job+date
  is Lee's bar; dateless rows can't join visits or spinelines). Guard: rerun scripts refuse
  to write undatable rows — they go to residue with reason.
- **IP-L9 — candidates are provisional until Lee's answer.** Date-intersection / proximity
  candidates NEVER promote to ties without Lee; they live in quarantine files, not the map
  (Lee's order, 10 Jul late eve).
