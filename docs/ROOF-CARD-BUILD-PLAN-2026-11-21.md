# Roof card build plan — 21 Nov 2026

Lee's ask, 21 Nov 2026: "I want every card working with every image on a billable event
timeline spineline for that card, as well as every doc that is right to be shared for that
job" — final estimate, terms sent in email, handover sheet sent in email, honesty box for
the planting type, every maintenance report in order, any diagnostic report. "We only link
install pics to the 'final balance' invoice and call it install." "Keep anything not yet
public as private but build out in full." Do it for every card, not only open ones.

Worked example, private preview: `~/scratch/image-plane-label-picker-20261121/card-preview-1592-23.html`.

## What the worked example (1592-23 38 Station Rd) taught
- **Invoices are the spine, and many carry no job code.** 4 of its 8 invoices have no
  job code in Xero; they were found by customer name and date (the ID ladder's Xero
  lane). Across all jobs about 300 invoices carry no job code.
- **Install = the final balance invoice** (INV-1131, "50% balance"). The advance carries no photos.
- **Visits exist without an invoice** (3 Apr 2025, 11 photos). These are flagged, never guessed.
- **GRA holds wrong facts**: install date 3 Sep 2025 (really April 2023); 9 report records
  for one visit. These are flagged, not changed.
- **Job folders hold strays**: a Lambeth quotation sits in the 1592-23 folder. A document is
  attached only when its own name or content carries this job's number.
- **Documents**: estimate in `Quotation/` (latest version), care agreement in `Project Pack/`,
  honesty boxes only for sedum and meadow (`Dropbox/Collateral`), GRR jobs have
  `Care Reports/` and `Site Investigation Reports/`. Emailed terms and handover sheets must
  come from Gmail, one roof at a time.

## Packages, in order
1. **Show `xxxx-yy` wherever Lee looks.** Display only. Breaks nothing.
2. **Change the stored job numbers to `xxxx-yy`.** First make about 30 readers in three
   programs (GRA app, image plane, Glengarry) treat 301-14 and 0301-14 as one job, with
   tests. Then pad 2,802 photo rows and the Mini A files, and rebuild 1,595 job pages.
   GRA's own code strips zeros today, so this is a real change across three programs.
   Needs Lee's yes before any GRA deploy.
3. **Billable events for every GRA roof, private.** One event per invoice (tagged, or found
   by customer name and date), install = final balance. Created as private visit records
   (`customer_visible = false`). Gaps and wrong GRA facts go on a flag list.
4. **Photos onto events, private.** Link and upload the 1,102 photos not yet in GRA; place
   every photo on its event by date and position. Nothing public.
5. **Documents, private.** BLOCKER: GRA documents have no private switch. Anything attached
   to a roof open to customers shows at once. So first add a "show to customer" switch to
   GRA documents (default off) — a small code change and a deploy, Lee's yes. Then, per roof:
   latest estimate, emailed terms and handover (one agent per roof reads the Gmail threads),
   honesty box by planting, care and diagnostic reports in date order.
6. **Roofs not in GRA.** 1,719 photos with invoices sit on roofs GRA does not hold. Lee
   picks which roofs to add (skill: gra-new-site).
7. **The weather account** — see below.

## The weather wording — judgement
The ChatGPT original was not found on either machine (it may sit in ChatGPT's own history,
or in the large Codex session logs that a search could not finish). The nearest is Lee's own
brief, `macminia:~/gra-work-records/handoffs/laptop-close-20261112/WEATHER-NARRATIVE-CORRECTION.md`.

**What is good, and must stay:** it starts from the purpose (this month, read against the
season and the year, then what it means for THIS roof and what to do next); it forbids
claims without evidence; it keeps the forecast apart from history and bans invented
medium-range forecasts; it names the roof facts that matter (planting, establishment, depth,
shade, irrigation, last visit); it bans generic advice; and it demands testing against
contrasting roofs.

**What is missing:**
1. **It is not what runs.** The live roof page (`weatherAccount.js`) uses fixed sentences
   chosen by plant type. A template cannot "connect" patterns. The brief needs a model that
   writes from an evidence pack, and a checker that refuses any sentence not backed by it.
2. **No defined evidence pack.** Each input should be named with its source: rainfall and
   temperature against normal (postcode_weather_history), the forecast and its horizon,
   planting, depth, shade, irrigation, the last visit's findings and recommendations, and the
   invoice lines (what was actually done: seeding, irrigation kit, feed).
3. **No rules per planting type.** The honesty box principles ("over-watering is worse than
   drought for sedum") should be written as rules the model must apply, one set per planting
   type. Shingle and riverbed have none yet.
4. **Beyond the image plane — the biggest gain.** Feed it what the photos show: bare areas
   from drought, moss encroachment tier, and the plant ID threats. What grows on a roof is a
   record of its moisture history. This closes Lee's 9 July chain: plant ID → conditions →
   weather match → recommendation → timing.
5. **No fixed shape.** Four parts every time: what happened; what is changing; what it means
   for this roof; what to do and when. Each sentence carries its kind: seen, measured,
   forecast or inferred.
6. **No golden set.** Three contrasting roofs, written once and approved by Lee, become the
   standard every new account is checked against.
7. **Timing.** The next-visit advice should name the window and the reason, for example
   after seed set, before the dry spell, or a spring feed.

## Update, 21 Nov evening — Lee's corrections
- **The visit is the event.** Lee: "the main thing is i was there on the date". A photo day is a
  visit and always appears on the card. The invoice is its label; when none is found the visit
  still shows, marked for the invoice search. Lee: "there will always be an invoice".
- **Photos sit inside each visit**, in the admin sidebar as on the customer page. Today the
  sidebar says "no album linked" and "No photos for this visit yet" where photos exist. This
  is a GRA admin change and joins package 3.
- **Match rate, all GRA roofs** (`visit_match.py`, read-only): 639 visits. Firm: 478 (75%) by
  job code, customer name or street on the invoice. Loose: 58 more (same job or customer
  invoiced within 200 days: yearly or combined billing) — leads, to be confirmed per roof.
  Left: 29 before the job's first invoice (survey or misfiled photo), 8 with no known customer,
  1 too recent, 65 unexplained. The Mini A invoice file may be incomplete; the live Xero
  connector would close part of the gap when it reconnects.

## Admin sidebar: showing private photos inside each visit — needs a security choice
How it works today (gra-continuation-20261112, read 21 Nov): the sidebar
(`src/components/JobVisitRecords.js`) asks `/api/portal/roof-photos?site_id=…` and keeps the
photos whose visit link matches. That route reads the photo store with the PUBLIC (anon) key
and asks only for `is_public = true`, and it drops photos on private visit days. So private
photos cannot appear in the sidebar by a small tweak: GRA's server is not allowed to read them.
Two ways to let ONLY an admin session see them (customer links never):
  A. Give GRA's server the photo store's full key, used only in the admin branch. Simple, but
     every GRA server path could then read and change the whole photo store. Not recommended.
  B. Add one narrow, read-only database function to the photo store that returns the photo
     fields for one roof, callable only with a dedicated key that GRA's server holds. GRA calls
     it only after its admin check. Recommended. It touches customer data and sign-in, so per
     the security practice it gets a changes-only security check before any deploy.
Either way: a GRA code change, a database change, tests, a security check, then a deploy on
Lee's yes.
