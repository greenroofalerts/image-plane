# F6B — flip page: 5-wide grid + short event headers + OR/GRR marker (spec)

**Date:** 2026-07-11 night · **Mandate (Lee, ledgered same day, verbatim):** "the phase
shopuld have grid of images 5 wide - the short descriptor of the event not the bill eg
site phase | RoofCare Spr 23 | Irrigation repairs July 24 etc" + "should be able to
distinguish ebtweenbilled by OR and billed by GRR and grouped accordingly - OR install,
GRR maintenance on same roof etc".

**Surface:** flip_server.py `/flip/<ref>` group rendering ONLY. Grouping logic, data
files, flip POST endpoint, index page, sister block, footer counts: UNCHANGED.

## 1. Group header — short descriptor, never the bill
- Format: `[OR|GRR|OR + GRR] <short descriptor>` — examples:
  `OR Install Jun–Nov 21` · `GRR RoofCare Spr 23` · `GRR Repairs Jul 24`.
- Company from the window's invoice `tenant` values: "Organic Roofs Ltd"→OR,
  "Green Roof Revival Limited"→GRR; both present→"OR + GRR"; windows with no
  invoices/tenant (unbilled visits) → no company marker. Render the company as a small
  distinct chip/badge before the descriptor so OR vs GRR is visible at a glance.
- Short descriptor map (phase → words + compact date):
  - Install → `Install <Mon–Mon YY>` (single month: `Install <Mon YY>`)
  - Spring roofcare → `RoofCare Spr YY` · Summer care and haycut → `RoofCare Sum YY`
    · Winter care → `RoofCare Win YY`
  - Repair → `Repairs <Mon YY>` · Leak detection → `Leak detection <Mon YY>` ·
    Diagnostic → `Diagnostic <Mon YY>` · Handover → `Handover <Mon YY>` ·
    Visit → `Visit <Mon YY>`
  - Month names 3-letter, year 2-digit. Derive from window start/end.
- The invoice line (numbers + dates + snippets) moves into a collapsed
  `<details>`-style element under the header labelled `Xero refs (n)` — the cross-ref
  Lee ordered stays one tap away, but the header line is clean. Still £-free.
- `Not yet matched to billing` group keeps its name + honest explainer, renders last.

## 2. Photos — 5-wide thumbnail grid per group
- CSS grid, 5 columns (narrow screens may wrap fewer — mesh/desktop is the target).
- Cells use THUMBNAILS (reuse the server's existing thumb route/cache — flip_thumbs /
  hash_thumbs2 conventions; never full-res in the grid; generate missing thumbs with
  the existing sips pattern if the server does that today — read the code first).
- Tap a cell → expand (inline or overlay) to the current full photo card: full image,
  date, lee_note caption, PRIVATE/PUBLIC state + flip button. Every photo keeps its
  flip control — collapsed into the grid ≠ unflippable.
- Tiny date chip on each cell (corner). Dedupe expander behaviour preserved
  (synthetic-only today).
- Lee-internal page: function over polish, but the grid must look tidy at one glance.

## Constraints (unchanged, priced in)
- Python 3.9 on Mini A. No £ anywhere. lee_note never leaves this page (Lee-internal).
- Working copy = laptop `~/image-plane/scripts/mini_a/flip_server.py`; scp to
  `macminia@192.168.178.61:~/image-plane/flip_server.py`; restart:
  kill old PID then `ssh macminia@192.168.178.61 "cd ~/image-plane && nohup python3
  flip_server.py > flip_server.log 2>&1 & disown"`. :8787 untouched.
- Doer self-checks ≠ done — orchestrator verifies (curl + screenshot) before commit.

## Verify-after (orchestrator)
1. Curl /flip/1124-19: header matches `OR Install Jun–Nov 21` pattern (regex on
   rendered HTML), invoice numbers present only inside the collapsed details block.
2. A GRR-billed roof page shows `GRR` chip; a mixed window (9 exist) shows `OR + GRR`.
3. Grid: page HTML contains the 5-column grid container; screenshot eyeballed — 5
   thumbs per row, date chips, tap-expand works (check one cell's expanded card
   includes the flip button).
4. £ grep = 0 on all checked pages; unmatched group still last; fallback banner roof
   (1051-19) unchanged; flip POST bogus id still 404.
5. Fresh screenshots to ~/leeos-private/image-plane-screens-f6/ (never the repo —
   .gitignore now blocks images by construction).
