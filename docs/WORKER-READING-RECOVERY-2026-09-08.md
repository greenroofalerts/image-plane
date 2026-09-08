# Worker reading recovery, 8 September 2026

Continuation of the existing Image Plane work. Base: daily-intake-worker
64f3ec0093d3e659b92c2149aacd2033514ac9e1. This change is prepared, not deployed.

The worker treated any prior reading-log entry as success. A failed thumbnail
could therefore count as read on retry. Cross-album reuse recorded only a marker,
so the filing and display code received no caption. Existing cabinet filenames
could also point at different bytes from the new row's recorded hash.

The repair requires successful caption and visible-writing results at the current
instruction version; retries failed, incomplete and obsolete readings; clears
false completion stamps; and recovers complete prior readings for reuse. Prior
readings are indexed lazily once per process, not rescanned for every image.
Successful unchanged readings do not repeat model calls. A cabinet name collision
preserves the existing file and refuses the incorrect association. Failed albums
produce an error result and nonzero exit while other albums continue.

Validation: 8 new offline recovery tests and all 31 existing teaching tests pass.
All data are synthetic; model, network and database operations are mocked.
No original customer data, runtime configuration or services were touched.

Before using this on Mini A, the existing owner must compare deployed versions
and preserve any newer changes, then check one real failed reading recovery and
one cross-album reused reading through the actual display. A collision remains
an explicit repair item; no existing photo is overwritten or reassigned here.

This is one required repair, not completion of the existing commission. Outstanding:
whole-source historical discovery, complete annotation recovery, the shared Spine
identity connection and correction updates, named billable-event grouping,
multiple keywords from Lee's existing vocabulary, and continuous automatic source
updates. Preserve existing ownership and source data; do not build a second store.

Read the maintained State of Play GREEN-ROOF-SPINE-BUILD-BRIEF.md for Lee's latest
continuation instructions. He was shown four pictures in GRA; the 63 figure was
an internal note, not his reported result. This is thousands of albums, not a
four-photo selection task. Nothing here proves unattended Mac operation.
