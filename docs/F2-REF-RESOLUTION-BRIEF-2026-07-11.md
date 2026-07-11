# BRIEF — Q2 ref-resolution deep sweep: c11, c13, c15 (2026-07-11)

Orchestrator: Fable (post-answers window). Doer: sonnet. Read-only sweep — you stage
NOTHING, you tie NOTHING, you edit NOTHING. Output = candidates + evidence + a
looked-in/could-not-look list per cluster (IP-L2 full-source rule).

Already swept THIS SESSION by the orchestrator (do not repeat): local Xero
sales/bill/spend lines (`~/leeos-private/pricing-study/xero/*.jsonl`) for
Horley/Gatwick/Hawley/RH6, word-safe Dover/CT15-17, BedZED/Dunster/Peabody/Bioregional
contacts, unpaid amount_due scan (c13 absent — NOTE: VOIDED invoices are excluded from
that pull, so never-paid-and-voided is invisible there); job_coords.json nearest-ref
(no hit <5km); Trello quarantine text grep for the area names (0 hits).

## The three clusters (Lee's words, 11 Jul dictation — ground truth)
- **c11**: "A job near Gatwick — 'Hawley' (UNCONFIRMED, likely Horley); HayBase roof on
  concrete structures; name not recalled, Lee expects us to find it."
  GPS centroid 51.158086,-0.115134 (Horley/Smallfield area).
- **c13**: "Contractor name forgotten — the company behind BedZED (South London); series
  of roof developments; THE ONLY JOB NEVER PAID FOR."
  GPS centroid 51.594488,0.144683 (Romford/Collier Row — the SITE, contractor is South London).
- **c15**: "Diagnostic inspection of a roof — 'I think it's the Dover area'."
  GPS centroid 51.134017,1.290259 (Dover proper). Word-boundary search only —
  plain 'dover' matches 'handover'.

## Sources to sweep, in this order (all local/house)
1. **Gmail mbox on Mini A** (`ssh macminia@192.168.178.61`, files `~/takeout-2026-06/*.mbox`).
   Use grep with context, not a parser. Terms: c11 → Horley, RH6, Gatwick, Hawley,
   Smallfield, "concrete" near "HayBase"/"hay base". c13 → BedZED, ZEDfactory, Dunster,
   Bioregional, Peabody, RM3/RM5/Collier Row/Romford + "green roof"; also chase-language
   ("outstanding invoice", "non-payment", "never paid", "write off", "county court",
   "final demand"). c15 → \bDover\b, CT15, CT16, CT17, "diagnostic" near Kent towns.
   Extract: From/To/Date/Subject + the matching lines. The mbox is 171k messages — grep,
   don't load.
2. **known_entities** (Supabase LeeOSplus `jrmcvuqtvrgehrthwtjz`, via the Supabase MCP —
   ToolSearch "supabase execute sql", read-only SELECTs only). Postcode prefixes RH6, RM,
   CT15/16/17; name ILIKE horley/gatwick/romford/dover/zed%.
3. **gra_stories** (Mini A `~/image-plane/grind/gra_stories.json`) — text search same terms.
4. **Trello quarantine** (Mini A `~/image-plane/grind/f2_trello_quarantine.json`) —
   this time by GEOCODE: rows whose geocoded lat/lon or evidence-card postcodes fall
   within 3km of each centroid (RH6*, RM3/RM5, CT15-17 prefixes too).
5. **Drive folder index** (Mini A `~/image-plane/grind/drive_folder_index.json`) — folder
   names containing the area terms. NEVER commit or copy this file anywhere.

## Rules
- Photo bytes never leave Mini A. No external calls except postcodes.io if needed.
- Every candidate needs an evidence line quoting the source verbatim (with date).
- A cluster with nothing found gets an explicit "looked in: [list] / could not look in:
  [list]" — never a bare "not found".
- Write results to `~/image-plane/docs/F2-REF-RESOLUTION-FINDINGS-2026-07-11.md` (laptop)
  — candidates per cluster, ranked, with evidence. No client-money amounts in the file
  beyond what identification needs.
- Return (final message): per cluster — best candidate(s) + one-line evidence, or the
  honest miss statement.
