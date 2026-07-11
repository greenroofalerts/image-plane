# F2 ref-resolution deep sweep — findings (2026-07-11)

Doer: sonnet subagent. Read-only sweep — nothing staged, nothing tied, nothing edited.
Sources swept in the order given in the brief: (1) Gmail mbox on Mini A via streaming
grep, (2) `known_entities` in Supabase `jrmcvuqtvrgehrthwtjz` via MCP read-only SQL,
(3) `gra_stories.json`, (4) `f2_trello_quarantine.json` by geocode + text, (5)
`drive_folder_index.json` by folder name. All work done on macminia@192.168.178.61 and
via Supabase MCP; no photo bytes left Mini A; no writes anywhere.

---

## c11 — RESOLVED ELSEWHERE, not re-derived

Orchestrator confirmed mid-sweep: **917-18 Lake Cottage** (Burstow/Smallfield area) is
already tied via batch `f2-clusters-r3-20260711`, confirmed by a plan photo Lee named
plus a Trello quarantine geocode 0.36km from the c11 centroid. This session's own
independent pass (run before the update arrived) found the identical record by the same
method — Trello quarantine row `job_ref=917-18`, card "917-18 Lake Cottage, Steve
Sanham" (board Revival Main), postcode RH6 9RF, geocoded 51.160347,-0.118828 — 0.36km
from Lee's stated centroid 51.158086,-0.115134. This corroborates the other window's
find; no further c11 work done here per instruction.

---

## c13 — "contractor behind BedZED, series of roof developments, only job never paid"

### Best candidate (unconfirmed BedZED link, strong geographic/contractor link)

**Job ref 823-17 "EcoGrove", Colliers Row Rd, Collier Row/Romford — contractor NTDL Ltd**

- Evidence (Trello quarantine, `f2_trello_quarantine.json`, address-only card, verbatim):
  card_name = `"823-17 EcoGrove, Colliers Row Rd, NTDL"`, board_name = `"OR MAIN"`,
  address_lines = `["Site Postcode:  Collier Row Road, RN5 2BG", "access via road to
  cattery to left of site gate"]`, dateLastActivity 2024-03-20.
  (Postcode "RN5" does not exist in the UK postcode system — near-certain typo for
  **RM5**, which is Collier Row, Romford — exactly Lee's GPS centroid for c13.)
- **No known_entities/Xero record exists for job_ref 823-17** — checked
  `job_ref ilike '%823-17%'`, `ilike '823-17%'`, `= '823-17'`, and
  `source_metadata::text ilike '%823-17%'` — all zero rows. Consistent with "never
  paid," with the brief's own caveat that the local Xero pull excludes VOIDED invoices,
  so this could mean either never-invoiced or invoiced-then-voided; known_entities can't
  distinguish the two.
- **Sibling job establishes the contractor and the "series":** job ref 832-17, Drive
  folder name `"832-17 Romford ZED"` (`1 OR/Projects/Pre 2023/2017`), and confirmed in
  known_entities:
  ```
  display_name: "NTDL Ltd", job_ref: "832-17", source: "xero",
  address: "Unit A | Codinton Way | Ashford | KentTN23 1AR",
  source_metadata: {invoice_count:7, total_paid_gbp:15900,
    invoice_numbers:[INV-0731,INV-0742,INV-0743,INV-0746,INV-0747,INV-0748,INV-0809],
    tracking_options:["832-17-COM-WPSED"],
    earliest_invoice_date:"2018-08-22", latest_invoice_date:"2019-08-22"}
  ```
  832-17 was **paid in full** (£15,900, 7 invoices, 2018–2019) — so 832-17 itself is
  NOT the never-paid job, but it proves NTDL Ltd is a real, repeat contractor doing
  more than one Romford-area green-roof job in the same period — matching "a series of
  roof developments."
- **Honest gap:** nothing in any source swept ties "NTDL Ltd" by name to BedZED,
  ZEDfactory, Bill Dunster, Bioregional, or Peabody. NTDL's Xero address is Ashford,
  Kent — not South London, which is how Lee described the contractor. This candidate is
  the strongest geographic/contractor match found but the BedZED identity link is
  **unconfirmed**.

### Other candidate considered and ranked lower
- Job ref 508-15 "7 Kings High School, Ley Street, Ilford," RM7 7LS (Trello
  quarantine, board "OR MAIN," dateLastActivity 2024-03-20). Postcode-prefix match on
  RM7 only (no geocode present, so proximity to the centroid can't be confirmed). A
  school, not a residential/eco housing development — doesn't fit "series of roof
  developments" as well as 823-17/832-17. Low confidence.
- Drive folder `"125-12-RGR Romford"` (2012) — surfaced by the "romford" term, no
  further content available (flat folder-name index only, no recursive listing). Too
  early (2012) and unexplained "RGR" — not pursued further.

### Sources swept for c13, verbatim evidence lines and misses
- **known_entities** (Supabase MCP, read-only SELECT): zero rows for
  `bedzed|zedfactory|dunster|bioregional|peabody` in display_name/address (orchestrator
  already swept contacts on this; this session reconfirmed against the full
  known_entities table, 882 rows, 40 with postcode / 455 with address / 882 with name).
  Only NTDL Ltd (832-17) surfaced from RM-prefix + name search.
- **gra_stories.json** (882 job-keyed entries): zero hits for any c13 term including
  `ntdl` — checked site.address/name/postcode and every story's prose/title.
- **f2_trello_quarantine.json** (901 rows, geocode + text): geocode pass (≤6km from
  51.594488,0.144683) returned zero rows with a *geocoded* lat/lon that close — 823-17
  has no geocode field at all (postcode-string only), which is why it didn't surface in
  the distance pass and only appeared via the postcode-prefix/text passes.
- **drive_folder_index.json** (1230 folders): "romford" → 125-12-RGR Romford, 832-17
  Romford ZED, 508-15; "collier row"/"bedzed"/"zedfactory"/"dunster"/"bioregional"/
  "peabody" as literal folder-name terms → zero.
- **Gmail mbox** (`~/takeout-2026-06/All mail Including Spam and Trash-002.mbox`,
  77GB / ~171,000 messages): **partial coverage only** — single-pass streaming grep
  (perl, word-boundary regexes) covered messages 1–~4,365 (~2.6% of the archive by
  message count) before this write-up; the file is enormous and some messages contain
  very long unwrapped lines (attachments/HTML) that slow a per-line regex pass
  substantially. Terms searched: ntdl, ecogrove, 823-17, 832-17, bedzed, zedfactory,
  dunster, bioregional, peabody, rm3, rm5, collier row, romford, plus chase-language
  (outstanding invoice, non-payment, never paid, write off, county court, final demand).
  **All "hits" in the covered portion were verified and are noise, not evidence**:
  - `term=romford`, msg 348: `"Metloc Business Hub, Suite 7, 37 Victoria Road,
    Romford, RM1 2LH"` — this is the debt-collection company **A S Collections'own
    office address**, from their marketing newsletter ("Struggling to Recover an
    Overdue Business Debt?"), not a Lee job.
  - `term=chase_outstanding`/`chase_countycourt`, several msgs: also from A S
    Collections' recurring newsletter ("This Week's Insolvency Report + Debt Recovery
    Support" / "No-Win No-Fee Debt Recovery") — generic marketing, not job-specific.
  - No hits at all for ntdl, ecogrove, 823-17, 832-17, bedzed, zedfactory, dunster,
    bioregional, or peabody in the ~4,365 messages covered.
  - **Looked in:** first ~2.6% of the mbox (messages 1–4365) by full-file streaming
    grep with word-boundary regex.
  - **Could not look in:** the remaining ~97% of the mbox (messages ~4366–171,000) —
    not completed in this session; script + hits file left on Mini A at
    `~/f2-ref-grep.pl` / `~/f2-ref-hits.txt` for a future window to resume or re-run
    with a faster tool (ripgrep is not installed on Mini A; plain grep -a would likely
    outperform the perl per-line approach and is worth trying first).

---

## c15 — "diagnostic inspection of a roof, I think it's the Dover area"

### Best candidate (circumstantial, unconfirmed site name)

**"Site survey" card, board "The Human Nature Partnership," Trello quarantine**
(`https://trello.com/c/MFlYWbJl`, dateLastActivity 2023-07-06, status `address_only_card`)

- Verbatim address_lines (order as extracted):
  ```
  Day 1 - 10 July - Beacon House (10 am), St Martins (3 pm)
  Day 2 - 11 July - Ethelbert Road (10 am),. Rivendell (2 pm), Coleman (1530)
  Day 3 - 12 July - Rosebud (9am), Oakwood (12 pm), 111 Tonbridge Road (2 pm),
    Highlands House (4pm)
  St Martins Hospital / Littlebourne Road, Canterbury, Kent / CT1 1TD
  11 Ethelbert Road, Canterbury, Kent / CT1 3ND
  Mill Lane, Eastry, Sandwich, Kent / CT13 0JX
  Hermitage Lane, Maidstone, Kent / ME16 9PH
  10-12 Calverley Park Gardens, Tunbridge Wells, Kent / TN1 2JN
  CT16 2AH   <- orphan postcode, no site name paired to it in the extracted data
  Manston Road, Ramsgate, Kent / CT12 6NT
  33-39 Birling Road, Leybourne, Kent / ME19 5HT
  111 Tonbridge Road, Maidstone, Kent / ME16 8JS
  Bow Arrow Lane, Dartford, Kent / DA2 6PB
  ```
- **CT16 2AH confirmed via postcodes.io as Dover** (admin_district: Dover, parish:
  Dover, admin_ward: Buckland) — the only allowed external lookup per the brief's
  rules, used only to resolve the postcode, no photo/PII data sent.
- Of the 9 named stops in the three "Day N" lines, 8 get a clean name+postcode pair in
  the list below them; **"Beacon House" (Day 1, 10am) is the one stop that never gets a
  paired postcode** — making it a plausible (NOT confirmed) match for the orphan CT16
  2AH line. This is an inference from list position, not a direct citation.
- Context on the client: "The Human Nature Partnership LLP" (OC428731, 4 Spur Road,
  Cosham, Portsmouth, PO6 3EB — per a separate card on the same board) runs a large,
  genuine institutional workstream with Organic Roofs — job refs with an "HN" prefix
  for NHS trusts and care homes appear repeatedly on this board (1051-19-HN Natural
  Resources Wales, 1055-19-HN East London NHS Trust, 1056-21 Homerton Hospital
  Foundation Trust, Kent & Medway Mental Health Trust, Townsend Court, etc.) — this is
  not a stray card, it's a real client relationship's board. The "Site survey" card is
  a multi-day, multi-site inspection tour, not literally titled "diagnostic inspection,"
  but it is a survey/inspection-genre card and the only Kent/CT-postcode item found
  anywhere in the sweep.

### Other candidate, ranked much lower
- Job ref 898-18 "Island Wall, Capra Developments," postcode CT5 1EE (Trello
  quarantine, board Revival Main, status `known_ref_new_address`). CT5 is Whitstable —
  roughly 30km from Dover proper, and outside the CT15/16/17 range Lee's centroid
  implies. Kept only for completeness; unlikely to be "the Dover area."

### Sources swept for c15, verbatim evidence and misses
- **known_entities**: zero rows for `dover`, `ct15/16/17`, `CT1%` postcode prefix, or
  `kent` in display_name/address/postcode, checked broadly (confirmed the ILIKE
  mechanism itself works — a sanity query for `%roof%` returned 11 rows).
- **gra_stories.json**: zero hits for dover/ct15/ct16/ct17 across all 882 entries.
- **f2_trello_quarantine.json**: geocode pass (≤6km of 51.134017,1.290259) returned
  zero rows with a close geocoded lat/lon (no row in the file has a geocoded point that
  close to Dover). Text/postcode pass across all 901 rows' `postcodes_found` and
  `address_lines` surfaced only the two candidates above. Also checked: every card in
  the file whose card_name contains "diagnostic" (11 cards, e.g. "1771-25 X&Why
  Fivefields - Diagnostic Inspection," "1809-25 Greenacres NP16 7NU Diagnostic
  Inspection") — **none of them have a CT-prefix postcode**; their postcodes span
  EC2A, SW1W, SE1, HA1, NP16, N19, N8, TN38, N5 — nowhere near Dover.
- **drive_folder_index.json**: zero folder-name hits for dover/ct15/ct16/ct17 across
  all 1230 folders. Also tried "beacon"/"human nature" as supplementary terms — found
  only unrelated 2016 folders ("628-16 25 Beaconsfield Rd, Ben Murdoch," "648-16 Beacon
  Hill House Annex") with no Kent/Dover connection; not pursued.
- **Gmail mbox**: same partial-coverage caveat as c13 (messages 1–~4365 of ~171,000).
  One apparent hit for `dover` (msg 1995, subject "Re: 1864-26 14 Alan Rd green roof
  estimate," from lee@organicroofs.co.uk to philip124johnson@gmail.com) was pulled in
  full and manually verified: it is **a false positive**, exactly the trap the brief
  warned about — the source text is `"PREGROWN MEADOW SPECS & HANDOVER.pdf"`, a
  standard template filename Organic Roofs attaches to every green-roof handover email.
  The MIME quoted-printable line-wrapping split "HAN" onto one raw line and "DOVER.pdf"
  onto the next, so a per-line `\bdover\b` regex matched it as if it were a fresh word
  at the start of a line — it isn't; decoded, it reads "HANDOVER.pdf." No genuine Dover
  hit found in the mbox portion covered. The `ct17` hit (msg 1181) and other CT-prefix
  hits were checked and are base64/PGP-armor noise (e.g.
  `"Ct17+24kLHn34GCZUXEhmYj/AKWeo9VojMEq6Zzv2KHubqwtbkeD..."`), not real postcode text.
  **Looked in:** messages 1–4365 (~2.6%) of the mbox, streaming grep, word-boundary
  regex, every apparent hit manually pulled and read in full context.
  **Could not look in:** the remaining ~97% of the mbox. Script/output left on Mini A
  (`~/f2-ref-grep.pl`, `~/f2-ref-hits.txt`) for continuation — **the sweep process
  (PID 77597 at time of writing) was left running in the background on Mini A**, so a
  later window can check `~/f2-ref-hits.txt` for further progress before re-running.

---

## Summary table

| Cluster | Status | Best candidate | Confidence |
|---|---|---|---|
| c11 | Resolved elsewhere | 917-18 Lake Cottage (batch f2-clusters-r3-20260711) | N/A — not re-derived here |
| c13 | Open | 823-17 "EcoGrove," Collier Row Rd, contractor NTDL Ltd (sibling 832-17 "Romford ZED" paid, confirms series) | Medium — strong geo/contractor fit, BedZED identity link unconfirmed |
| c15 | Open | "Site survey" card, Human Nature Partnership board, CT16 2AH (Dover, confirmed via postcodes.io), possibly "Beacon House" by list position | Low-medium — genuine Dover postcode, but site-name pairing and "diagnostic" framing are inferred, not quoted |

---

## Orchestrator corroboration (Fable, same day — own queries, local Xero pull)

c13 = **823-17 EcoGrove, Collier Row Rd** hardened from "best lead" to strong candidate:
- `xero-bill-lines.jsonl` holds ONE 823-17 line: Darren Ray (sub-contractor labour),
  "3,4,6 sept 823-17 EcoGrove, Collier Row Rd", £450, dated 2018-10-10 — tracked under
  sibling option 832-17-COM-WPSED. We PAID labour for 823-17.
- `xero-sales-lines.jsonl` holds ZERO 823-17 lines (grep this turn) — no customer invoice
  ever tracked. Money out, none in = "the only job never paid for".
- c13 photo path-dates: 2018-08-06 → 2018-08-21 (22 photos) — the same job window.
- NTDL Ltd 832-17 sales include Dec-2018 lines for "materials removed/confiscated without
  permission from Romford" — the relationship visibly soured.
- Still UNCONFIRMED: the "company behind BedZED" descriptor (NTDL's Xero address is
  Ashford, Kent; no name-link found to BedZED/ZEDfactory/Bioregional/Peabody). The ref
  evidence stands without it; Lee's glance decides.

Tie proposal (Lee-gated, nothing staged): Mini A `grind/c13_tie_proposal_20260711.json`.
