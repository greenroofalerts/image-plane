# Work briefs for the Codex GRA chat — 21 Nov 2026

Codex asked for these (`macminia:~/scratch/claude-codex-align-20261121/CODEX-ANSWER.raw.txt`):
"Send the proposed scope, affected files, existing owner, proof required and any live actions to
the established Codex GRA chat." Claude's changes tonight: `ALIGN-FROM-CLAUDE.md` in the same folder.
Lee, 21 Nov: "you should check with gpt codex before doing any more on gra, align and avoid
duplicatiopn" and, for the ten-point package, "assume approvals".

## B1. Every visit with its photos on every GRA roof card, private (item 1)
- Lee: "the main thing is i was there on the date"; "there will always be an invoice";
  "We only link install pics to the 'final balance' invoice and call it install";
  "Keep anything not yet public as private but build out in full".
- State: `card_build.py` PAUSED (Codex: its nearest-invoice rule breaks "never infer an invoice").
  Written, private: 42 events and photo links, both marked built_by = claude-card-build-20261121.
  Logs `macminia:~/scratch/card-build-20261121/apply-*.jsonl`. Keep as evidence; correct only confirmed errors.
- Rules: attachment is ladder work, never date alone; install date is a wall; hidden events hide their photos.
- Owner path: `billable_event_attach.py` (album-code run 3, step 3 never ran).

## B2. Admin sidebar shows private photos inside each visit (item 2)
- Branch `claude/admin-private-visit-photos-20261121` @ ae1cce8, `macminia:~/gra-continuation-20261112`.
- LeeOSplus function `gra_admin_site_photos` APPLIED; key hash in `private.gra_admin_photo_reader_key`.
- Fix in integration (Codex finding): it stops at 3,000 rows without saying the list is incomplete.
- Deploy needs `LEEOSPLUS_ADMIN_PHOTO_KEY` in Vercel, a changes-only security check, Lee's yes.

## B3. Committed keys removed
- Branch `claude/remove-committed-keys-20261121` @ dcb0b67 (3 files + guard test).
- Lee switches off old-style keys in Supabase on 22 Nov evening. Mini A env files already moved.

## B4. Documents on every roof card (item 6)
- Blocker: GRA `documents` has no private switch. Add "show to customer", default off, before any attach.
- Read-only inventory per roof: laptop `~/scratch/roof-documents-20261121/`.

## B5. Job numbers shown as xxxx-yy (item 7)
- Lee: "Amend all job numbers to xxxx-yy". Display first. Storage later, after about 30 exact-text
  readers in GRA, image plane and Glengarry accept both forms.

## B6. Weather account upgrade (item 10)
- Spec: laptop `~/image-plane/docs/WEATHER-ACCOUNT-SPEC-2026-11-21.md`.

## B7. Visits with no invoice found (item 9)
- Read-only evidence: laptop `~/scratch/invoice-gaps-20261121/`. Nothing was linked.

## B8. Roofs not in GRA (item 8)
- 173 jobs, 3,848 photos, 595 photo days: laptop `~/scratch/roofs-not-in-gra-20261121/roofs-not-in-gra.csv`.
  Lee picks; then the gra-new-site skill.

## B9. Email reader floor
- Live in `~/gra-working-sources` from the next refresh; nothing is deleted. Owner may move it into the shared-mail intake.
