# Questions for Lee — image-plane (LEE-411)

Plain-language decisions queued from the scaffold session, 2026-06-09.
None of these block running the pipeline; defaults are in place for all.

1. **Where is the photo library going to live while we parse it?** The
   MacBook has about 12 GB free, which fits the model and the database
   but not a full Takeout archive. If the export is on an external
   drive or one of the Minis, the pipeline runs fine pointed at any
   folder — but tell me the target and I'll sanity-check space first.

2. **Is roughly 4–5 seconds per photo acceptable?** (Exact number in
   docs/BENCHMARK.md.) For a 50,000-photo library that's a couple of
   days of background captioning. It's resumable, so it can run in
   overnight chunks — but if you want it faster we should run it on a
   Mini or accept a smaller/weaker model.

3. **What should happen to duplicates?** Right now the pipeline only
   *records* them (which copy duplicates which, and how close). It
   never deletes anything. Do you want a "move dupes to a review
   folder" command, or is the report enough?

4. **How aggressive should "near duplicate" be?** The current setting
   catches re-encodes, resizes and brightness tweaks of the same shot,
   but deliberately does NOT merge burst shots or crops. If you'd
   rather group "basically the same moment" photos, that's a looser
   threshold — easy to change, worth a decision.

5. **What do you want captions FOR?** If the end goal is search
   ("show me photos of the van at a job site"), the next step after
   captioning is a search command over captions+tags. If the goal is
   feeding the memory spine or another system, the schema should get
   an export format. The answer changes what gets built next.

6. **HEIC: is your iCloud export HEIC or JPEG?** HEIC is supported,
   but if your export is all HEIC I'd add a HEIC-specific test pass
   before the real run.
