# Image Plane label set — draft, 21 Nov 2026

Source: Lee's own list, 21 Nov 2026 (quoted at the end). This draft replaces every
earlier label scheme for the photo screens. Nothing in the data is changed by this
document. It is a draft for Lee to correct.

## The rule in one line

Six filters, short fixed lists, one name for one thing, and a "good example" star
on any label. A photo gets only the labels that apply. Most photos get two or three.

## The seven filters

### 1. Site / job ref
- Search by job ref, address, postcode or client.
- Already on the Photos screen. 9,776 of the photos in the store already carry a job.

### 2. Radius from a place
- Pick a place (a postcode, a tap on a map, or "this site"), then a distance:
  100 m · 500 m · 1 km · 5 km.
- Uses the photo's own location. 9,286 photos have one.
- New. Simple to add.

### 3. Vegetation type (per photo, or none)
- **sedum**
- **meadow** (includes shingle / riverbed planting — Lee, 21 Nov 2026)
- **no green roof (waterproofing only)**
- A photo that shows both sedum and meadow gets both. There is no "mixed"
  value. "Mixed" was a script's word (`build_roof_tick.py:93`) for a roof whose
  record had both ticked; Lee did not know the term (21 Nov 2026).

### 4. Components (any number per photo)
- filter fleece
- drainage / reservoir
- geotextile protection layer
- substrate
- alu (perimeter)
- alu separator
- irrigation
- habitat feature
- pebble channel

### 5. Plant ID (species, any number per photo)
- Species only, never vegetation type.
- Starts from the 40 names already in `label-eval/rules.py` (Sedum acre,
  Sedum album, Sedum rupestre, Armeria maritima and so on). Lee adds names.
- Only on photos where a plant can actually be named.
- Includes **lichen** (Lee, 21 Nov 2026: "Lichen ok").
- Includes **moss** (Lee, 21 Nov 2026: "Put them in"). Named to species when
  it can be; plain "moss" when it cannot.

### 6. Structural (any number per photo)
- internal valley gutter
- skylight
- parapet / coping (one label — Lee, 21 Nov 2026: "Keep them together")
- masonry (wall)
- metal capping
- soil pipe / vent
- solar panels (Lee, 21 Nov 2026: "Put them in")

### 7. Roof condition (any number per photo, or none)
Lee, 21 Nov 2026: "roof condition fliterable by vegetation/membrane".
Two halves, so you can filter by either one.

**Vegetation condition**
- moss encroachment, in tiers: under 25% · 25–50% · 50–75% · over 75%
  (Lee agreed these four tiers, 21 Nov 2026: "Yes, use them")
- bare areas (drought)
- bare areas (overwatering) — **PINNED 21 Nov 2026: Lee will explain what
  overwatering looks like later.** No photo found in 723 checked. Do not
  guess at it until he has.
- more to be added later

**Membrane condition**
- leak repair: every kind of repair (patches, seams, upstands and so on)
- leak diagnostic: photos taken on a diagnostic inspection
- Lee expects these "might need more sorting". Sub-labels wait until the
  photos are seen in groups.

Moss appears twice on purpose. Plant ID says "moss is here". Vegetation
condition says "how much of the roof the moss has taken".

## Good example

- A star goes on a photo **for one label**, not on the photo as a whole.
  A photo can be a good example of "pebble channel" and not of "parapet".
- Limit: 20 stars per label. The screen refuses a 21st until one is removed.
- Project packs choose only from starred photos.
- First candidates for stars: the photos Lee already called "BEST PRACTICE" or
  "good example" in his spoken notes (June–July 2026 captures,
  `~/leeos-private/image-plane-captures/`). Each becomes a suggested star on the
  label his note names. Lee confirms it with one tap.

## Coverage

- Target: at least one photo for every value in filters 3 to 6.
- The screen shows a photo count beside every value, and shows a value with
  no photos in red.
- Every count is a count of photos, not of jobs.

## What happens to the old labels

- The old words are **hidden, not deleted**. Lee's own notes (535 photos)
  stay searchable as free text.
- Old words that map straight across (to be applied after Lee agrees):

| New label | Old words that become it |
|---|---|
| sedum | sedum (model), sedum (Lee), pregrown sedum, sedum modules, xeroflor |
| meadow | pregrown wildflower, seeded wildflower / meadow, plug & seed, haybase, shingle / riverbed / plug-seed, shingle (riverbed & bank) |
| (each photo re-labelled sedum and/or meadow) | mixed |
| no green roof (waterproofing only) | waterproofing / leak-repair, not a green roof, epdm |
| alu (perimeter) | perforated_aluminium_edging |
| alu separator | aluminium_separator |
| drainage / reservoir | drainage_reservoir_board, drainage-reservoir-board |
| irrigation | irrigation_pipe_or_misting, irrigation |
| pebble channel | pebble_or_gravel_border, pebble_border, pebble-border |
| filter fleece | filter-fleece |
| habitat feature | habitat_feature, logs, hibernacula |
| skylight | skylight |
| parapet / coping | parapet, parapet_coping (the 3,728 machine guesses), coping |

- Machine labels already exist for about 12,300 photos from an earlier
  model pass (`grind/vision_categories.jsonl`). They are a first guess, never
  a label. They show as a suggestion with a dashed outline, and become a label
  only when Lee taps them. That rule is already in the tap screen code.

## Questions for Lee — all settled 21 Nov 2026

1. SETTLED 21 Nov 2026: shingle is meadow; "mixed" is dropped (see filter 3).
2. SETTLED 21 Nov 2026: parapet and coping stay one label, "parapet / coping".
   No split by eye.
3. SETTLED 21 Nov 2026: moss goes in plant ID, solar panels go in structural.
4. SETTLED 21 Nov 2026: issues live in filter 7, roof condition.
5. SETTLED 21 Nov 2026: moss tiers are under 25%, 25–50%, 50–75%, over 75%.

## Dry run, 21 Nov 2026 — how many photos already fit each label

Read-only. Nothing was written. Script and full counts:
`macminia:~/scratch/claude-label-dryrun-20261121/` (`label_dryrun.py`,
`label-dryrun-counts.json`). It read all 10,034 photo rows.

Three sources are kept apart, because they are not equally trustworthy:
- **Lee tag**: a tag Lee gave.
- **Lee note word**: a word found in Lee's own spoken note (weaker: the word
  may be in the note without the thing being in the photo).
- **Machine guess**: an old model guess. Only 8,488 photos have one (the
  iCloud set). Photos added since have none.

| Filter :: label | Lee tag | Lee note word | Machine guess |
|---|---:|---:|---:|
| vegetation :: sedum | 34 | 86 | 2,325 |
| vegetation :: meadow | 14 | 47 | 1,216 |
| vegetation :: no green roof | 8 | 0 | 0 |
| components :: filter fleece | 5 | 58 | 0 |
| components :: drainage / reservoir | 2 | 77 | 1,717 |
| components :: geotextile protection layer | 1 | 4 | 0 |
| components :: substrate | 4 | 29 | 0 |
| components :: alu (perimeter) | 7 | 18 | 2,428 |
| components :: alu separator | 7 | 12 | 0 |
| components :: irrigation | 3 | 23 | 1,903 |
| components :: habitat feature | 9 | 68 | 0 |
| components :: pebble channel | 13 | 46 | 3,596 |
| plant ID :: moss | 14 | 26 | 1,675 |
| plant ID :: a named species | 0 | 13 | 0 |
| structural :: internal valley gutter | 1 | 18 | 0 |
| structural :: skylight | 6 | 19 | 1,348 |
| structural :: parapet / coping | 5 | 25 | 2,840 |
| structural :: masonry (wall) | 1 | 2 | 0 |
| structural :: metal capping | 0 | 13 | 0 |
| structural :: soil pipe / vent | 0 | 3 | 0 |
| structural :: solar panels | 0 | 9 | 866 |
| condition :: moss encroachment | 1 | 4 | 0 |
| condition :: bare areas (drought) | 6 | 22 | 0 |
| condition :: bare areas (overwatering) | 0 | 2 | 0 |
| condition :: leak repair | 4 | 10 | 0 |
| condition :: leak diagnostic | 57 | 22 | 0 |

Good-example candidates from Lee's own words ("best practice", "good
example"): 10 photos.

### The machine guesses are not good enough to show

A sample of 8 random machine-guessed photos, checked by eye (Claude), 21 Nov:
about half were right. Pebble channel 1½ of 2, parapet / coping 1 of 2,
solar panels 1 of 2, drainage board 0 of 2. Several photos carry 7 or 8
guesses at once, so the model said yes to almost everything. Eight is too
few for an error rate, but enough to say: **do not show these guesses as
suggestions in bulk.**

### What this means

- Every label already has at least one photo by Lee's tag or note, except
  "a named species", "metal capping", "soil pipe / vent" and "bare areas
  (overwatering)", which rest on note words only.
- Lee's target is at least one good photo per label, and up to 20 good
  examples. That does not need all 10,034 photos labelled. It needs a
  short, strong list of candidates for each label, which Lee then stars.
- So the next step is a fresh look per label with a stronger eye, building
  about 30 candidates per label for Lee to star, not a relabel of
  everything.

## Candidate run, 21 Nov 2026 (Lee: "Claude may look")

- 723 photos judged by Sonnet agents against all 26 labels (brief:
  `~/scratch/image-plane-label-picker-20261121/judgements/JUDGE-BRIEF.md`).
  Pools: Lee's tags and note words first, then 222 random photos, then 137
  photos from roofs GRA flags for moss, bare patches, stress or irrigation.
- Claude checked 12 top-rated picks by eye: 12 of 12 labels right, 1 over-rated.
- Picker sheet: `~/scratch/image-plane-label-picker-20261121/good-example-picker.html`,
  446 numbered photos, up to 20 per label, repeats removed. Code-to-photo list:
  `codes.json` beside it. Nothing written to the photo store.
- Coverage: 25 of 26 labels have a usable photo; 24 have one rated a good
  teaching photo. **"bare areas (overwatering)" has none.** Thin: geotextile
  protection layer (4), moss encroachment (5), named species (9).

## Lee's words, 21 Nov 2026

> i need to be able to filter by
> 1 site/.job ref
> 2 radius from given location (that might be new but shouldnt be hard)
> 3 vegetation type (sedum, meadow, no green roof/waterproofing only)
> 4 components (filter fleece, drainage/reservoir, geotextile protection layer, substrate, alu (perimeter), alu separator, irrigation, habitat feature, pebble channel
> 5 plant id: species not vegetation type
> 6 structural: internal valley gutter, skylight, parapet, masonry (wall), masonry (coping), metal capping, soil pipe/vent,
>
> i want to be able to mark things as good example of up to 10 or twenty of each that i can use to select from when building project packs for isntallers to refer to
> i want MAINLY at least one result for each relevatn category (not all pics iwll have plant id or need it, not all pics will have components or striuctural etc)
