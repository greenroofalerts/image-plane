# Green Roof Visual Corpus — Delivery Sequence Map
*Anchored to LEE-411 (child of Memory Spine LEE-391). By the Stage-Mapping Contract. 2026-06-30. Status: DRAFT.*

## Honest current position
A Lee-driven **spike, not yet a systematic build.** Off LEE-411's spec in three ways, by choice or oversight:
1. Skipped Phase-0 landscape scan (built custom on local qwen3-vl, didn't evaluate Roboflow/CVAT/FiftyOne).
2. Used iCloud photos, not the Drive corpus (LEE-398).
3. Stored in local JSONL on Mini A, not the `visual_observations` spine table.

**Real output (all on Mini A, valid uniform JSONL, keyed by photo + job):**
16,426 photos described + provenance · 12,668 kept · 2,419 *date-valid* job matches (date gate added today) · 89 reports ingested · register 91→129 geocoded · 35 of Lee's own labels.

## Three efficiency decisions — make consciously, don't accrete silent debt
- **D1 Landscape scan.** Keep local qwen for now (works, sovereign; the moat is Lee's labels, not the tool) — BUT do the scan *before* building any custom labelling UI from scratch. *Decision: Lee.*
- **D2 Source.** iCloud now; add the Drive corpus (LEE-398) when LEE-411 un-parks. *Decision: Lee.*
- **D3 Storage.** Local JSONL now (spike); migrate to `visual_observations` (spine) on un-park. Migration is cheap — data is structured + keyed by path/job. *Decision: Lee.*

## Ordered next task-sets (each has ONE proof gate)
- **1.1 Visit-bundle** *(now)* — group each job's date-valid photos by date; attach its diagnostic/maintenance report. **Proof gate:** open one job → its visits, each = photos + the report, dated. *(LEE-411 Phase 1 "discoverable by site/year/visit" + Lee's bundling ask, raised ×4.)*
- **1.2 Taxonomy YAML** — turn the label-tags into a version-controlled category list **Lee owns and edits**. **Proof gate:** `taxonomy.yaml` exists; Lee can add/rename a category. *(LEE-411 Phase 2: "Lee owns the categories, not the model.")*
- **1.3 Pre-tagged waves + measure** — carousels pre-tagged against the taxonomy; voice corrections append to `knowledge_notes`; measure model-vs-Lee agreement. **Proof gate:** Lee labels 50 in <X min; agreement % on a held-back set. *(LEE-411 Phase 2 success signal.)*

## Not yet — named so it can't sprawl
Diagnosis models (Phase 3) · installer PWA (Phase 4) · spine migration · Drive backfill — each starts ONLY after 1.1–1.3 prove. No new feature before its gate.
