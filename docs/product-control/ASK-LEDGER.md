# ASK LEDGER — image-plane (LEE-411) — Lee's rulings, quoted and dated

Rule: any ask, correction or rejection Lee makes about this project enters
here the SAME DAY, quoted and dated, by the window that heard it. Lee's words
outrank every summary, report, and handover. Newest at top.

## 2026-07-11

- **Active-job rule for Trello-found refs** (morning, on the 284 new refs): "if no invoice
  for 24 months working back from today they are not active, and should be used for mining
  images, typology, profit, lccation etc but not distort 'live ations'" → Rule: activity =
  ≥1 invoice in the trailing 24 months; inactive refs are mining/knowledge material only
  and must never generate live actions or workload.
- **OR/GRR cross-company job numbers** (morning): "or installs, grr maintains - very
  possible and the code will often share same nnnn-yy but with a maintenance related
  bookjepeping suffix: sometimes same place will have two different job numbers eg 2
  olympic mews which has green roof maintannfcen and waterproofing repairs last year" →
  Same NNNN-YY across companies (or with a maintenance suffix) = same roof candidate;
  same site can legitimately carry two distinct numbers. Extend the sister-ref rule.
- **No workload for non-active jobs** (morning, on continuous candidate engine): "yes but
  dont create workload for non-active jobs, passive value add is fine and good."
- **Weather×plants dynamic database ambition** (morning, verbatim core): "we want to
  create a dynamic maching database for weather patterns capturedf by the weather feeds
  in each postcode, look at all the pictures we've taken there, use the comments from
  reports/next visit recommendations and build a historic dyanmic database of what plants
  have done well and what have not how much irrigation is needed, what are companion
  species, and also use this to read the last 12-24 months weather make reocmmendations
  for what to do at site visits … could combine this with a social sentiment camillo
  style search of gfardening blogs and bbc website and news sources … modelling of what
  is working, and what to do about it in specification phase of green roofs (Organic
  Roofs - becoming a job discovery phase) and ongoing care" → VISION AMBITION; needs its
  own vision-stage-mapping canon session before any build.
- **Old GRA click-to-reveal weather guidance wanted back** (morning): "the click to
  reveal guidance monitoring on weather guidance that the OLD gra had new one not yet
  would help with that" — GRA-side item, noted here for the weather×plants thread.
- **Company-archive angle: think on it more** (morning, on the corpus as 15 years of
  the business in pictures — book/retrospective material): "haha interesting add that
  as a thing to think about some more."
- **Mini A backup ordered and done same morning** ("do it now"): Mini A had NO Time
  Machine destination. Now: nightly 03:50 cron tarball of the critical set (ground truth,
  ledgers, allocation, quarantine, docs, scripts; site_view excluded as regenerable) to
  ~/backups/image-plane/ keep-14, plus first off-machine copy pulled to laptop
  ~/Backups/image-plane-mini-a/. Guard: cron survives reboots; log at backups/backup.log.
- **Project view public/private (Glengarry, spoken in this window)**: "i specifically
  asked for a 'project view' of every card that has a job number which is basically its
  GRA card with a public and private facing side - at the ooint of sharing, everything
  that doesnt need to be pricvate can be flipped public" — belongs in Glengarry's Ask
  Ledger; the Glengarry prompt Lee was given instructs that window to enter it there.
  Berkeley Square card (not clickable) named as the live use case.

## 2026-07-10

- **F2 CANDIDATE PASS + F3 READINESS mandate — Lee's order VERBATIM** (late eve; ratified
  with "go in new window, handover"; copied here on pickup by the executing window,
  2026-07-10, per the handover's first-act instruction):

  > IMAGE-PLANE — F2 CANDIDATE PASS + F3 SPINELINE READINESS
  >
  > BUILD PREFLIGHT (print before any code):
  > Source of truth: job_coords.json + ground-truth file + Xero invoice dates + Trello boards
  > + photo EXIF. Runtime can know: dates, geocodes, job refs, tie evidence. Evidence tiers:
  > confirmed ties = validated; date-intersection candidates = provisional, NEVER promoted
  > without Lee's answer. Files allowed: sheet builder, new candidate scripts in
  > ~/image-plane/, docs. Forbidden: ground-truth file (append-only via capture loop only),
  > counts.py logic, guards, anything in GRA/Glenross. Stop wall: 3 fails on any step = STOP.
  >
  > STEP 1 — DATES ↔ INVOICES CANDIDATE ENGINE. For each of the 20 mystery clusters and the
  > 33 ambiguous photos: take the cluster's photo-date span, query Xero invoice/visit dates
  > (local data already mined) for jobs active in that window ±14 days, intersect with GPS
  > proximity where the cluster has coordinates. Output per cluster: ranked candidate list
  > (max 3) with the evidence line for each ("invoiced 12–18 Mar 2022, 0.4km from cluster
  > centroid"). Candidates are provisional. No tie is written. Quarantine file, not the map.
  >
  > STEP 2 — TRELLO SWEEP. The boards are the canonical job record and were never checked.
  > Pull cards, extract job refs + addresses + dates, geocode postcodes, diff against the
  > 419-job map. New addresses land in quarantine with source=trello. Then re-run Step 1
  > scoring with Trello dates included. Report yield honestly, including zero if that's the
  > truth.
  >
  > STEP 3 — REBUILD THE SHEETS WITH CANDIDATES. Each cluster page now opens with its ranked
  > candidates as tap/say-able options ("1. Litten Path — invoiced that week, 0.4km. 2. …
  > 3. None of these / other") with the evidence line under each, keeping free dictation as
  > the fallback. Operator language only — no source enums, no scores in raw form. Same
  > ground-truth capture path as 2 July, unchanged.
  >
  > STEP 4 — F3 SPINELINE READINESS AUDIT (read-only, no F3 build). For each of the 238 roofs
  > with photos: sort photos by EXIF timestamp; count photos missing EXIF; flag any roof where
  > EXIF order contradicts album/filename order or known visit dates. Output
  > SPINELINE-READINESS.md: per roof — photo count / % with usable timestamps /
  > order-conflict flags / READY or NEEDS-RULE. Propose (do not implement) the fallback
  > ordering rule for NEEDS-RULE roofs. F3 does not start until Lee has seen this file.
  >
  > FINAL REPORT, separated tiers, each YES/NO with reason: code exists / guard passed /
  > tests passed / browser proven (sheets curl-checked with candidate blocks rendering) /
  > live proven / data-truth proven (candidate evidence lines spot-checked against 5 real
  > Xero rows and 5 real Trello cards, quoted). Plus ledger checked / rules applied / new
  > entries / files touched / forbidden untouched / commit hash / unresolved walls. DONE only
  > if sheets render with candidates in the browser; otherwise "code shipped, not verified".
  > No tie count may increase this run — attribution advances only through Lee's answers.
  >
  > Cherny per-step X/100, Chain Y/100 self-gate header; rewrite if <97.

  Ratification words: "go in new window, handover". Source handover:
  ~/leeos-private/HANDOVER-2026-07-10-IMAGE-PLANE-CANDIDATE-PASS.md.

- **Every Lee surface states what Lee should DO** (late eve, on opening
  verdicts.html cold): "ive opened that verdicts and have no idea what you
  want from me / are yiou still working on this under preagreed protocols and
  pathways to attributkon or not?" → Ruling: an answer sheet is not ready for
  Lee unless it states, on the page, how to answer and that it feeds the
  pre-agreed dictation→ground-truth loop (2 Jul contact-sheet protocol —
  which remains THE attribution pathway, unchanged). Rendering, sizes and
  language passing is not an operator pass; "does Lee know what to do next"
  is the test. Guard: how-to-answer blocks now built into build_f2_phaseL.py
  headers (all three surfaces), not pasted into HTML.

- **Full-source rule for location evidence** (eve window, mid-F2, after an
  agent declared 413 jobs "no evidence" from folder names + invoice text
  only): "why are you only looking in folder names? there are dociuments in
  all of the drive folders / we ahve already done this work and gotten
  addresses for most / if you look at gmail too? / we literally have a set
  process for identifying where something is? / this is has DEFINITELY
  ALREADY BEEN DONE!!" → Ruling: no "no evidence" claim for a job's location
  unless the FULL established process ran — existing harvested stores (see
  `F2-ADDRESS-STORES-INVENTORY-2026-07-10.md`), Gmail, and the documents
  INSIDE the Drive folders — not just the cheap layers. Guard: inventory doc
  + skill hard rule added same night; half-search rule applies.
- **The big-picture frame** (eve window): "are you looking at this only as a
  bookkeeping tool? does the delta work extend to the bigger picture? if so
  how, no jargon" → Standing expectation: allocation/address work is only
  ever in service of the canon promise (roof life-story pages, customer
  surface, plant knowledge, marketing) and gets explained in those terms,
  plainly.
- **The go** (this window's opening): Lee pasted
  `HANDOVER-2026-07-10-IMAGE-PLANE-DELTA.md` back with the F1→F8 order
  restated — taken as the go for F1 + F2 machine passes; GRA customer swap
  stays its own session; F5 (memory spine) and F8 (answer sheets) stay
  Lee-gated.
