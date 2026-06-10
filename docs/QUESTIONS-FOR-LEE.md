# Decisions — image-plane (LEE-411)

The six open questions from the 2026-06-09 scaffold session, answered
by Lee 2026-06-10. These are the operating decisions for the build.

1. **Working location: this MacBook, locally.** ~41 GB free should fit
   the library; external SSD if not. Google Drive is delivery only,
   never the working location. **Rule: sanity-check free space against
   the export size when it lands, before ingesting.**

2. **Speed: 7 s/photo sequential is accepted.** Overnight chunks, no
   sharding across machines. Keep it simple.

3. **Exact duplicates: delete command approved** — byte-identical
   (same sha256) only. Next build item; not built yet.

4. **Near-dupes and bursts: no hard deletes.** Keep the best of each
   group, move the rest to a quarantine/review folder. The detector
   earns deletion rights only after it is proven on real photos.

5. **Captions feed a domain intelligence layer — green roof business
   evidence.** Direction for the next module (PLANNED, not built —
   awaiting morning sign-off):
   - Domain tagging: plant species, substrate type (shingle / pregrown
     meadow / haybase), roof system details (EPDM, alu trim), defect
     types.
   - Site matching: GPS + date against the GRA sites table.
   - Later stage: fork personal photos to separate streams (football
     grounds; holidays).

6. **Formats: assume both HEIC and JPEG.** First step when the export
   arrives: test HEIC handling on real samples before any bulk run.

## Agreed next steps (in order)

1. When export lands: free-space check, then HEIC spot-test on real
   samples.
2. Build `image-plane dedup --delete-exact` (byte-identical only) and
   a near-dupe quarantine command (move, never delete).
3. Domain tagging + GRA site-matching module — design first, sign-off
   before build.
