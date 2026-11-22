# Questions for Lee — image plane, 21 Nov 2026

Everything below waits on you. Nothing here has been done. Most important first.

## 1. Pick the good examples (the main one)
Open the picker sheet (sent to you as a file) and reply with the codes you want
starred, for example "SED03 PEB01 PEB07". Say "not PEB04" for any photo that is
wrong. Nothing is written to the photo store until you reply.

## 2. Save the stars and labels to the photo store?
When you have picked, may I write your stars and the labels you confirmed to
the photo store on Mini A? It adds fields; it changes no photo and makes
nothing public. (Your 12:35 stop order to the Grok bots says "stop GRA and
Image Plane", so I am asking, not assuming.)

## 3. Commit the label set?
The label set and this list sit uncommitted in `~/image-plane/docs/` on the
laptop. May I commit them on the current branch? Copy them to Mini A too?

## 4. Delete the ask board?
You said "the ask board is a fucking catastrophe and should be deleted".
Deleting the tables cannot be undone. Yes or no? (Nothing will be written to
it meanwhile.)

## 5. The overnight builds left three loose ends
- The live tap screen needs one restart to show the Gundreda album.
- The GRA "confirmed" line for Gundreda was never written (lock busy).
- The 11:30 album-code run stopped part way: 12 albums filed, 38 held,
  16 GRA timeline lines not written.
Leave all three, or pick them up here?

## 5b. ANSWERED 21 Nov: overwatering is PINNED — Lee will explain it later.
<!-- was: Overwatering photos
No photo of bare areas from overwatering was found in 723 checked, even on
roofs with irrigation and bare patches. Can you name a job where it happened,
so I can look there? Otherwise the label stays empty until a visit shows it. -->

## 6. ANSWERED 21 Nov: lichen goes in plant ID ("Lichen ok").
<!-- was: Lichen
The photo checkers found lichen (for example cup lichen) on roofs. It is not on
your label list. Add "lichen" to plant ID, or leave it out? -->

## 7. ANSWERED 21 Nov: clean up yes — done, all six temporary folders removed.
<!-- was: Clean up
About 720 small copies (512 px) of roof photos were made for the checkers.
The safety guard blocked me deleting them, and asks for your approval. They
are only copies; the originals are untouched, and the picker sheet keeps its
own thumbnails. Say yes and I will remove these two folders' JPEGs:
- laptop: `/private/tmp/claude-501/-Users-Lee/50672d8d-b505-4e41-ad8c-a24121ce172c/scratchpad/cand*/img*`
- Mini A: `~/scratch/claude-label-candidates-20261121/img*` -->

## 8. ANSWERED 21 Nov: "Grok is stood down you build".

## 9. Photos linked to billable visits that customers cannot see (audit 21 Nov)
Read-only audit, mirroring the GRA roof page code (gra-continuation @b885e3f).
1,101 photos sit on a GRA roof and are linked to a billable visit (a GRA visit
record within 3 days of the photo, or an invoice already on the photo). 272
show today. 829 do not, across 41 roofs. On the 7 roofs customers can open:
1059-19 84 Culverden Rd 16 · 1394-21 42 Hodford Rd 21 · 1513-22 6-8 New North Rd 13 ·
1592-23 38 Station Rd 8 · 1751-24 5 Lebanon Park 12 · 1864-26 14 Alan Road 35 ·
1900-26 Linklater Pavilion 21.
Proposed, in order, nothing done yet:
  A. Private, no customer sees it: link 218 photos to their GRA roof and upload
     178 files to GRA's private store.
  B. Screen all 829 with Claude for anything that should not be public (people,
     documents, non-roof) and show you what is held back.
  C. On your yes, make the rest public, the 7 open roofs first, and check one
     roof page as a customer sees it.
Two things stand in the way: the photo-write hold the overnight bot set
(~/image-plane/PHOTO-WRITE-HOLD.json on Mini A, "no public photos" under the
Grok brief), and your 12:35 stop. Lifting the hold for this one job is your call.
Separately: 3,978 photos sit on GRA roofs with no GRA visit record near their
date (GRA holds only 426 visit records), and 4,714 belong to jobs with no GRA
roof at all. Both are bigger packages for later.

## 10. Plant ID pilot (done 21 Nov, waiting on your eye)
500 photos from 31 roofs with maintenance, read by Claude (Sonnet), threats
first. Sheet: `~/scratch/image-plane-label-picker-20261121/plant-id-pilot.html`.
41 firmer threat sightings, 189 possible (folded away), 150 plant names.
Claude checked 8 firm threats by eye: every plant name held; 2 were not on a
roof (a ground-level bed, a neighbour's wall). A real sycamore seedling in a
sedum mat was found. Reply "yes T001" or "no T004"; "right S03" or "wrong S03 is …".
Next if you like it: the same pass over all roofs, and a plant card per species.

## 11. Recount with invoices and location (Lee: "Billable event is an invoice", "Use geo data")
Supersedes the counts in question 9. Read-only, Mini A, 21 Nov.
- 5,936 of 10,033 photos link to an invoice (same job, invoice within 60 days
  of the photo). 508 invoices have at least one photo.
- 4,217 of those are on roofs GRA knows (242 placed by photo location, not job code).
  1,719 are on roofs GRA does not hold at all — GRA's reach, as you suspected.
- On GRA roofs: 690 show to customers; 2,425 are already in GRA privately and
  only lack "public"; 1,102 need linking or uploading first.
- Of the 21 roofs customers can open, 14 show NO photos at all today.
- 2,816 photos have no label of any kind.
- Fault found and fixed in the count: GRA writes some jobs with a leading zero
  (0301-14) and the photo store without (301-14); the first audit missed them.
Nothing public, per your ruling. Question: may I do the PRIVATE part now —
link and upload the 1,102 so they sit ready in GRA, unseen by customers? It
needs the overnight photo-write hold lifted for this one job.

## 12. Roof card build (plan: ~/image-plane/docs/ROOF-CARD-BUILD-PLAN-2026-11-21.md)
Preview of one roof built out in full, private: ~/scratch/image-plane-label-picker-20261121/card-preview-1592-23.html
a. Is the preview the shape you want? If yes, I build packages 3 and 4 for every GRA
   roof, all private. (The overnight photo-write hold gets my job added to its allow list.)
b. GRA documents have no private switch: anything added to an open roof shows at once.
   May I add a "show to customer" switch to GRA documents (default off)? It is a small
   code change and needs a deploy.
c. 1592-23 has a spring 2025 visit (11 photos) with no invoice anywhere. How was it billed?
   (One example of a class; the build flags all of them.)
d. The ChatGPT weather wording is not on either machine. Can you find the chat and paste it?
e. There is no honesty box for shingle or riverbed planting. Write one, or use meadow?

## 13. The private build is ready but needs ONE step from you (21 Nov)
Practice run over every GRA roof (Mini A ~/scratch/card-build-20261121/plan-all-182828.json):
118 roofs, 595 visits, 327 new PRIVATE visits, 239 existing visits reused, 5,680 private
photos placed inside their visits (620 uploaded first), 29 days left alone because public
photos sit on them. Invoices: 440 firm, 32 loose, 123 not found yet.
The writes are blocked by the overnight photo-write hold. The safety check would not let me
add my build to its allow list myself. Your options:
  - Say in chat, in your words, that I may add "claude-card-build-20261121" to the allow list
    of ~/image-plane/PHOTO-WRITE-HOLD.json on Mini A. Publishing stays refused either way.
  - Or add it yourself: the file's "allow_writers" list, one entry.
Separately, so you can SEE the private build: the GRA admin sidebar must show private photos
inside each visit. That is a GRA code change and a deploy; it needs its own yes.

## 14. Seeing the private build in your admin sidebar
The sidebar can only show public photos today, by design of its security rules. To show
private photos inside each visit to you alone, I recommend option B in the plan (a narrow,
read-only lookup only GRA's admin side can call), with a security check and a deploy on your
yes. Go ahead with option B?
