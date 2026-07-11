# FINDINGS — Q4 plant/moss IDs (lee_followups items 15–20), 2026-07-11

**Everything below is MODEL OPINION, not ground truth.** Vision model: qwen3-vl
(local) via Ollama on Mini A. num_ctx 4096, no format:json, thinking left on,
sequential, one image per call. HEIC converted to JPEG on Mini A via `sips`
(magic bytes ffd8 verified), fed as base64, /tmp copies deleted after. Photo
bytes never left Mini A. Nothing here enters knowledge_notes, guards, or any
Lee/client surface — Lee's dictation loop decides what sticks.

Caveat on reliability: qwen3-vl gave **different IDs across frames of the same
plant** and a clearly broken run on 20b (dozens of near-duplicate Polytrichum
lines before self-correcting). Treat low-conf answers as near-noise. Reported
verbatim and honestly.

---

## Item 15 — c1, "crassula-coloured but NOT crassula", top-3 wanted
3 frames, each a separate single-image call (multi-image at num_ctx 4096 returned empty).

**IMG_2979.JPG** (first call empty; retried once, succeeded):
- Sedum acre — model: qwen3-vl (local), conf 90/100
- Sedum spectabile — conf 70/100
- Sedum × rubrotinctum — conf 50/100
- Invasive: "no invasive threat seen"

**IMG_2982.JPG:**
- Stellaria media (common chickweed) — conf 70/100
- Poa annua (annual bluegrass) — conf 60/100
- Cerastium fontanum (mouse-ear chickweed) — conf 50/100
- Invasive: "no invasive threat seen". Model: "no Sedum species present" on this frame.

**IMG_2987.JPG:**
- Sedum acre — conf 85/100
- Sedum spurium — conf 70/100
- Sedum × rubrum — conf 60/100
- Invasive: "no invasive threat seen"

Note: the model contradicts itself frame-to-frame (Sedum on 2979/2987, chickweed
on 2982). No stable single answer. Its leading guess across frames is a **Sedum**
stonecrop (acre most often), which is genuinely NOT genus Crassula — consistent
with Lee's "crassula-coloured but not crassula" phrasing, but unverified.

## Item 16 — c2 (IMG_3439.JPG), "long mat-forming clumps", top-3
- Bryum argenteum (silver roof moss) — model: qwen3-vl (local), conf 95/100
- Tortula ruralis — conf 70/100
- Pleurozium schreberi (feather moss) — conf 50/100
- Invasive: "no invasive threat seen". "no Sedum species present".

## Item 17 — c4 (IMG_7930.HEIC), CONFIRM/DENY corncockle / cornflower / oxeye daisy
Model denied all three, each at 0/100:
- Corncockle (Agrostemma githago): **absent**, conf 0/100
- Cornflower (Centaurea cyanus): **absent**, conf 0/100
- Oxeye daisy (Leucanthemum vulgare): **absent**, conf 0/100
- Invasive: "no invasive threat seen". "no Sedum species present".

## Item 18 — c7 (IMG_8178.HEIC), near-ground plant, top-3
Model output was muddled (listed Sedum candidates then a separate grass list):
- Lawn grass — conf 95/100
- Sedum spurium — conf 90/100
- Creeping thyme — conf 30/100
- Sedum reflexum — conf 10/100
- Dandelion — conf 15/100
- Invasive: "no invasive threat seen". Leading read: manicured lawn grass with
  possible stonecrop; low coherence.

## Item 19 — c8 (IMG_7245.HEIC), describe + ID, top-3
Model description: "garden/roof area, dark soil, dense small rosette-forming
succulents (pinkish-red leaves), moss, small green plants."
- Sedum spurium — model: qwen3-vl (local), conf 85/100
- Sedum acre — conf 75/100
- Sedum rubrocanescens — conf 50/100
- Invasive: "no invasive threat seen". Named each Sedum individually per rule.

## Item 20 — c12 moss (5 frames), incl. Lee's "cup on a long stand"
Each frame a separate call. Model consistently reads the stalked/cup structure as
a **Polytrichum** capsule-on-seta (haircap moss), which matches "cup on a long
stand" (pedicellate capsule / splash-cup). Consistent across all 5 frames.

**IMG_8158.HEIC (20a):**
- Polytrichum commune — conf 80/100 ("capsule on long seta, stalked structure present")
- (spurious Sedum lines 70/60 — moss photo, disregard)

**IMG_8159.HEIC (20b):** run degraded — model spat dozens of near-duplicate
Polytrichum lines then self-corrected. Usable answer:
- Polytrichum commune — conf 70/100 ("capsules on long setae matching 'cup on a long stand'")
- Polytrichum formosum — conf 30/100

**IMG_8160.HEIC (20c):**
- Polytrichum commune — conf 85/100
- (spurious Sedum rubrum 60 / Sedum acre 50 — disregard, moss photo)

**IMG_8165.HEIC (20d):**
- Polytrichum commune (common haircap moss) — conf 70/100
- "Capsules on long setae bearing cup-like capsules" — consistent with Polytrichum.

**IMG_8166.HEIC (20e):**
- Polytrichum commune — conf 90/100
- Polytrichum formosum — conf 30/100
- "Stalked capsules (setae) with cup-shaped splash-cups; characteristic of Polytrichum."

Item 20 verdict (model opinion): the "cup on a long stand" is a **Polytrichum
(haircap moss) capsule on a seta**, ~70–90/100 across frames. Species most likely
P. commune; P. formosum a weaker second. Unverified.

---

## Infra notes
- No other job was running on Mini A GPU when this started (ollama serve up,
  no model loaded). Nothing was killed.
- One empty response (15a first attempt); retried once and it answered. All other
  12 calls returned text. Zero consecutive infra failures.
- Multi-image calls at num_ctx 4096 returned empty — ran every image as its own
  single-image call, which is why item 15 and item 20 are broken out per frame.
