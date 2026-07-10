# SPINELINE-READINESS.md -- F3 pre-build audit (STEP 4, read-only)

Generated 2026-07-10T22:07:36Z by `f3_spineline_readiness.py` on Mini A. This is an AUDIT ONLY -- the F3 spineline build has NOT started. Candidates and ordering rules proposed below are PROVISIONAL (IP-L9): nothing here has been written as a tie, and nothing here changes the corpus.

## Summary

- Roofs audited: **238**
  Counted by: distinct `job_ref` among allocated_keeps (`grind/allocation_v2.jsonl` rows not present in `grind/allocation_v2_flags.jsonl`) -- replicates counts.py's join, run this session, matching `python3 counts.py` -> "roofs with tied photos: 238".
- READY: **228** / NEEDS-RULE: **10**
  Counted by: per-roof verdict logic in this script -- READY iff % usable-EXIF >= 80% AND zero EXIF-vs-path-date conflicts (>180d gap).
- Total tied photos across the 238 roofs: **8111**
  Counted by: `sum(len(paths) for each job_ref group)` over the same join.
- Overall % with usable EXIF timestamp: **97.9%** (7943 / 8111)
  Counted by: `mdls -name kMDItemContentCreationDate` batched over every present-on-disk allocated-keep path (missing-on-disk paths excluded from mdls calls, counted as 0 usable directly from `grind/kept_missing_on_disk.json`).
- Site-name quality: **148 real** / **86 synthetic (derived label, not a proper site name)** / **4 missing (ref + postcode only, no name anywhere)**
  Counted by: `resolve_site_name()` fallback chain per roof -- `grind/site_names.json` -> `grind/gra_stories.json` -> `grind/job_coords.json[site]` -> postcode-only label -- tallied over the same 238-roof loop. "Synthetic" = a machine-generated `known_entities` evidence label (e.g. "contact/entity: X") reformatted for readability, not a real site name -- flagged so this is never mistaken for a proper name on a Lee surface.

### FINDING -- album-order check has 0 photos to check against today

The spec's order-conflict check lists "EXIF order vs album order (takeout album names) vs filename order vs known visit dates." Checked: **0** of the 238-roof join's photos come from the takeout ledger.
Looked in: `grind/allocation_v2.jsonl` rows for the 238 job_refs, filtering by `'takeout' in path`. Every takeout row in `allocation_v2.jsonl` is either `excluded` or flagged `non_keep_path` (because `classified.jsonl` -- the keep/drop/quarantine verdict source -- never covers takeout paths at all, per counts.py's own comment), so 0 takeout photos are counted as "tied" in the current 238-roof set. Could not look in: whether a FUTURE allocation run adds takeout photos into the keep-verdict path (would require `classified.jsonl` to gain takeout coverage first -- out of scope for this read-only step). The album-vs-EXIF check is implemented in the script (dormant) so it activates automatically if that ever changes; today it fires 0 times, correctly, not by omission.

### FINDING -- photo_ledger_merged.jsonl `ts` is not a photo date

The spec names `photo_ledger_merged.jsonl` as a corroborating "ledger date" source. Checked: its only timestamp field is `ts`, decoded to 2026-06-26 for the first rows checked -- that is when the captioning pipeline ran, not when the photo was taken. It carries no per-photo capture-date field. It was NOT used as a date source in this audit (using it would have manufactured a false corroboration). Looked in: the full key set of 2,000 sampled rows (`path, sha256, model, model_digest, prompt, response, host, ts` -- no date/day/captured field present). Could not look in: whether an older/newer version of this ledger elsewhere on Mini A carries a real date field -- only the current `~/image-plane/photo_ledger_merged.jsonl` was checked.

### Flag histogram (photo-level, across all 238 roofs)

Counted by: tally of every per-photo `flags` entry written in `grind/spineline_readiness.json`.

- `exif_vs_pathdate_conflict`: 7
- `no_exif_missing_on_disk`: 168
- `no_known_visit_near_photo`: 1339

## Per-roof table

| Site | Photos | % usable EXIF | Missing-on-disk | Flags | Verdict |
|---|---:|---:|---:|---|---|
| BN1 3DG (1-11) | 22 | 100.0% | 0 | - | READY |
| Priory Ticehurst (1009-19) | 11 | 90.9% | 1 | - | READY |
| Parison Close (1031-19) | 3 | 100.0% | 0 | - | READY |
| Dulwich Prep (1032-19) | 7 | 100.0% | 0 | - | READY |
| Ready Steady Go King Henrys Ave (1037-19) | 28 | 100.0% | 0 | - | READY |
| Lockhart St (1040-19) | 10 | 100.0% | 0 | - | READY |
| Birdlip (1047-19) | 65 | 100.0% | 0 | - | READY |
| 84 Culverden Rd SW12 (Sophie Dexter) (1059-19) | 46 | 100.0% | 0 | - | READY |
| Bromley By Bow (1062-19) | 6 | 100.0% | 0 | - | READY |
| Loke (1068-19) | 35 | 91.4% | 3 | - | READY |
| E8 1BG area (unnamed site) (1074-19) [synthetic label] | 25 | 100.0% | 0 | - | READY |
| 40 The Rise Sevenoaks (1077-19) | 30 | 100.0% | 0 | - | READY |
| SE23 1NL area (contact: Sarah & Tom Parker-Shemilt) (1079-19) [synthetic label] | 12 | 100.0% | 0 | - | READY |
| NW6 6EE area (contact: Natasha Hidvegi) (108-12) [synthetic label] | 1 | 100.0% | 0 | - | READY |
| PMH Whitechapel X&Why (1080-19) | 130 | 97.7% | 3 | - | READY |
| Dram House (1099-19) | 63 | 93.7% | 4 | - | READY |
| 445 New Cross Road (1106-19) | 28 | 100.0% | 0 | - | READY |
| 25 Trinity Crescent (1124-19) | 83 | 98.8% | 1 | - | READY |
| N1 0QJ area (contact: Chris Dyer) (1133-20) [synthetic label] | 5 | 100.0% | 0 | - | READY |
| E17 6QW area (unnamed site) (1136-20) [synthetic label] | 2 | 100.0% | 0 | - | READY |
| TN4 9QT (1164-20) | 4 | 100.0% | 0 | - | READY |
| 10 Palace Court Gdns (1173-20) | 21 | 100.0% | 0 | - | READY |
| Badminton School (1176-20) | 105 | 99.0% | 1 | - | READY |
| Vera Road (1180-20) | 6 | 100.0% | 0 | - | READY |
| BN44 3PU area (contact: Matthew Wintersgill) (121-12) [synthetic label] | 3 | 66.7% | 1 | low_exif_coverage | NEEDS-RULE |
| 54 Cavell St (1210-20) | 34 | 94.1% | 2 | - | READY |
| 1 Cavendish Mews (1218-20) | 9 | 88.9% | 1 | - | READY |
| E3 5AH area (contact: Charlie Fawcett) (1219-20) [synthetic label] | 4 | 100.0% | 0 | - | READY |
| W12 8BU area (contact: Ella Zimina) (1226-20) [synthetic label] | 12 | 100.0% | 0 | - | READY |
| E9 5DX area (contact: Matt Webb) (1288-21) [synthetic label] | 1 | 100.0% | 0 | - | READY |
| E2 0QN area (contact: Four Corners Film Ltd) (1290-21) [synthetic label] | 10 | 100.0% | 0 | - | READY |
| 161 Fawe Park Rd (1301-21) | 116 | 98.3% | 2 | - | READY |
| HP16 0HJ area (contact: Holy Trinity Church) (1303-21) [synthetic label] | 2 | 100.0% | 0 | - | READY |
| Clarence House Richmond (1308-21) | 99 | 100.0% | 0 | - | READY |
| 2a Ensor Mews (1319-21) | 28 | 100.0% | 0 | - | READY |
| SE6 4AY area (contact: Elizabeth Farrant) (1320-21) [synthetic label] | 26 | 96.2% | 1 | - | READY |
| Victoria Park Bowls Club, Portslade (1321-21) | 36 | 100.0% | 0 | - | READY |
| 32 Nicosia Rd (1340-21) | 54 | 94.4% | 3 | exif_vs_pathdate_conflict | NEEDS-RULE |
| RBKC 2025 GREEN ROOF (1343-21) | 86 | 100.0% | 0 | - | READY |
| GRA sub-site variant of 1343-21, address=Avondale Park (building in the centre of the park), Walmer Road, London W11 4EY (1343-21-AVP) | 3 | 100.0% | 0 | - | READY |
| GRA sub-site variant of 1343-21, address=Little Wormwood Scrubs, Dalgarno Gardens, London W10 5LL (1343-21-LWS) | 10 | 90.0% | 1 | - | READY |
| GRA sub-site variant of 1343-21, address=St Luke's Gardens (toilet building next to the playground/play area), Cale Stre (1343-21-STL) | 52 | 96.2% | 2 | exif_vs_pathdate_conflict | NEEDS-RULE |
| 49 Gundreda Rd M Lockwood (1352-21) | 40 | 97.5% | 1 | - | READY |
| 10 Strathray Gdns (1357-21) | 21 | 100.0% | 0 | - | READY |
| Streat Hill Farm (1364-21) | 125 | 96.0% | 5 | - | READY |
| 53 Deodar Rd (1367-21) | 39 | 94.9% | 2 | - | READY |
| 16 Shipton St (1371-21) | 11 | 100.0% | 0 | - | READY |
| BS40 7XD area (unnamed site) (1377-21) [synthetic label] | 11 | 90.9% | 1 | - | READY |
| Town Hall RBKC Hornton St (1379-21) | 103 | 99.0% | 1 | - | READY |
| E6 3HS area (contact: Laura Jordan-Rowell) (1380-21) [synthetic label] | 10 | 100.0% | 0 | - | READY |
| 31 Barrowgate Rd (1392-21) | 10 | 100.0% | 0 | - | READY |
| 42 Hodford Rd (1394-21) | 45 | 97.8% | 1 | - | READY |
| TW7 6QA area (unnamed site) (1398-21) [synthetic label] | 4 | 100.0% | 0 | - | READY |
| 23 Remington St (1410-21) | 10 | 100.0% | 0 | - | READY |
| 25 The Plantation (1423-21) | 15 | 100.0% | 0 | - | READY |
| W8 6LU area (contact: RBKC) (1425-21) [synthetic label] | 1 | 100.0% | 0 | - | READY |
| W13 9TJ area (contact: David Cheshire) (1426-21) [synthetic label] | 4 | 100.0% | 0 | - | READY |
| (unnamed -- no site name anywhere) (1428-21) | 49 | 100.0% | 0 | - | READY |
| 36a Lawford Rd (1429-21) | 8 | 100.0% | 0 | - | READY |
| Point A (1440-21) | 66 | 100.0% | 0 | - | READY |
| BN2 9YG area (contact: Ben Simmonds) (1446-21) [synthetic label] | 9 | 88.9% | 1 | - | READY |
| SW4 0QP area (contact: Hatty Hopkins) (1447-21) [synthetic label] | 14 | 92.9% | 1 | - | READY |
| RG42 5NY area (contact: Lyndon Hedderley) (1448-21) [synthetic label] | 5 | 100.0% | 0 | - | READY |
| SE22 0SD (145-12) | 2 | 100.0% | 0 | - | READY |
| SW5 9AN area (contact: TUPA Energy Ltd) (1457-21) [synthetic label] | 1 | 100.0% | 0 | - | READY |
| 17 Thurleigh Rd SW12 (1459-21) | 38 | 94.7% | 2 | - | READY |
| 48 Ryedale (1465-21) | 72 | 100.0% | 0 | - | READY |
| 9 Chepstow Villas (1470-21) | 26 | 100.0% | 0 | - | READY |
| NW5 1UT area (contact: Property AV Ltd) (1472-21) [synthetic label] | 8 | 100.0% | 0 | - | READY |
| EC1V 2NX (1475-22) | 4 | 100.0% | 0 | - | READY |
| NW6 1JP area (unnamed site) (1480-22) [synthetic label] | 28 | 92.9% | 2 | - | READY |
| 2D Granville Rd DA14 4BN (1481-22) | 14 | 100.0% | 0 | - | READY |
| 3 Loxford Gdns (1486-22) | 50 | 100.0% | 0 | - | READY |
| 36 Baskerville Rd, Elaine SW18 3RS (1488-22) | 43 | 100.0% | 0 | - | READY |
| KT2 6HE area (contact: Olivia Besser) (1489-22) [synthetic label] | 13 | 100.0% | 0 | - | READY |
| Richardson's Yard, Brighton (149-13) | 6 | 100.0% | 0 | - | READY |
| Marmont/Goldsmith (Acorn Mgmt) (1496-22) | 53 | 100.0% | 0 | - | READY |
| Elephant Park (1501-22) | 42 | 100.0% | 0 | - | READY |
| Corsica St (1506-22) | 1 | 100.0% | 0 | - | READY |
| BN7 1LJ area (contact: Juliette Mitchell) (151-13) [synthetic label] | 1 | 100.0% | 0 | - | READY |
| 13 Devereux Rd (1528-22) | 26 | 100.0% | 0 | - | READY |
| NW8 8RE area (contact: Morgan Clark Ltd) (1535-22) [synthetic label] | 22 | 95.5% | 1 | - | READY |
| 52 Melody Rd (1539-22) | 32 | 100.0% | 0 | - | READY |
| 19 Withdean Cres (1546-22) | 15 | 100.0% | 0 | - | READY |
| Plus X (1548-22) | 5 | 100.0% | 0 | - | READY |
| E3 5RE area (contact: Melissa Norman) (1554-22) [synthetic label] | 7 | 100.0% | 0 | - | READY |
| 57b Josephine Ave (1562-22) | 31 | 100.0% | 0 | - | READY |
| 71 Highgate West Hill (1575-25) | 35 | 94.3% | 2 | - | READY |
| 1577-22 -133 Nevill Rd - N16 0SU (1577-22) | 23 | 100.0% | 0 | - | READY |
| Cairncross Mews (1582-22) | 17 | 94.1% | 1 | - | READY |
| 3 Crowns (1584-22) | 15 | 100.0% | 0 | - | READY |
| 1a Downhurst (1588-23) | 27 | 100.0% | 0 | - | READY |
| 38 Station Rd (1592-23) | 116 | 95.7% | 5 | - | READY |
| 11 Lidfield Rd N16 9NA (1595-23) | 15 | 93.3% | 1 | - | READY |
| 10 Strathray Gdns (1598-23) | 18 | 100.0% | 0 | - | READY |
| Chaucer Rd (1600-23) | 29 | 93.1% | 2 | - | READY |
| 6 Malvern Rd Green Roof (1606-23) | 40 | 97.5% | 1 | - | READY |
| SW19 4PQ area (contact: Paula Cawthorne) (1614-23) [synthetic label] | 9 | 88.9% | 1 | - | READY |
| 85 Windsor Rd (1626-23) | 31 | 90.3% | 3 | - | READY |
| Mona Rd (1633-23) | 17 | 94.1% | 1 | - | READY |
| SE12 8LQ area (contact: Sara Geddes) (1634-23) [synthetic label] | 11 | 100.0% | 0 | - | READY |
| 117a Bellenden (1635-23) | 13 | 100.0% | 0 | - | READY |
| N3 1HG area (contact: Tamara Rabin) (1636-23) [synthetic label] | 10 | 100.0% | 0 | - | READY |
| E3 5BP area (contact: Rachel Sorrill) (1639-23) [synthetic label] | 7 | 100.0% | 0 | - | READY |
| SW19 5HA area (contact: Rahul Srinavasan) (1640-23) [synthetic label] | 28 | 96.4% | 1 | - | READY |
| Flora Gardens (misfiled 2016 photos; own ref pending) (1641-23) | 75 | 100.0% | 0 | exif_vs_pathdate_conflict | NEEDS-RULE |
| AUT 24 SLGC GREEN ROOF (1646-23) | 22 | 100.0% | 0 | - | READY |
| RPOAT Inner Circle Regents Park (1667-23) | 59 | 100.0% | 0 | - | READY |
| 42 Rutherford House Battersea Rise SW11 4BT (1673-23) | 15 | 93.3% | 1 | - | READY |
| N7 0HE (1674-23) | 10 | 100.0% | 0 | - | READY |
| NW8 8RE area (contact: Mr K Okyere) (1676-23) [synthetic label] | 5 | 100.0% | 0 | - | READY |
| SW8 1FY area (contact: Sean Sullivan) (1687-24) [synthetic label] | 20 | 100.0% | 0 | - | READY |
| Kingston Parish Pavilion (1692-24) | 38 | 100.0% | 0 | - | READY |
| E5 0LF area (unnamed site) (1697-24) [synthetic label] | 25 | 96.0% | 1 | - | READY |
| 147 De Beauvoir (1701-24) | 85 | 100.0% | 0 | - | READY |
| THE HICKMAN (1703-24) | 61 | 96.7% | 2 | - | READY |
| SILCHESTER RD (1704-24) | 86 | 100.0% | 0 | - | READY |
| Riverside East, Peppermint Events (1705-24) | 159 | 100.0% | 0 | - | READY |
| 10DPR (1712-24) | 79 | 92.4% | 6 | - | READY |
| TN3 0TJ area (contact: Nick Smith) (1717-24) [synthetic label] | 26 | 96.2% | 1 | - | READY |
| Tungate (1723-24) | 53 | 96.2% | 2 | - | READY |
| 22 Mill Rd Lewes (1724-24) | 82 | 97.6% | 2 | - | READY |
| 2 Patten Rd (1726-24) | 36 | 97.2% | 1 | - | READY |
| W7 2EW (1727-24) | 31 | 100.0% | 0 | - | READY |
| High Trees, Melbourne Derbyshire (1729-24) | 51 | 100.0% | 0 | - | READY |
| NW6 1DZ area (contact: Ceclia Yee) (174-13) [synthetic label] | 3 | 100.0% | 0 | - | READY |
| Lloyd Park Waltham Forest (1742-24) | 149 | 100.0% | 0 | - | READY |
| 123 Goodhart (1743-24) | 12 | 100.0% | 0 | - | READY |
| 24 Warwick Ave (1744-24) | 27 | 100.0% | 0 | - | READY |
| SW2 2BN (1746-24) | 3 | 100.0% | 0 | - | READY |
| Bridge (1747-24) | 54 | 100.0% | 0 | - | READY |
| SG12 9NN (1748-24) | 16 | 87.5% | 2 | - | READY |
| UB7 0GB area (unnamed site) (175-13) [synthetic label] | 1 | 100.0% | 0 | - | READY |
| SE1 9SG area (contact: Opera PM) (1750-24) [synthetic label] | 7 | 100.0% | 0 | - | READY |
| 5 Lebanon Park, Twickenham (1751-24) | 20 | 100.0% | 0 | - | READY |
| 20 Elmhurst (1753-24) | 8 | 100.0% | 0 | - | READY |
| 31 EMBLETON RD (1754-24) | 15 | 100.0% | 0 | - | READY |
| Lambeth SUDS (Jessop Sumner) - 19 Reedworth SE 11 4PH (1755-24) | 189 | 98.4% | 3 | - | READY |
| 7 Hambledon (1760-25) | 68 | 100.0% | 0 | - | READY |
| (unnamed -- no site name anywhere) (1770-25) | 28 | 96.4% | 1 | - | READY |
| 52 Pensford Ave TW9 (1782-25) | 90 | 98.9% | 1 | - | READY |
| Cosbycote Ave (1784-25) | 27 | 100.0% | 0 | - | READY |
| Kippford (1787-25) | 31 | 100.0% | 0 | - | READY |
| (unnamed -- no site name anywhere) (1790-25) | 38 | 94.7% | 2 | - | READY |
| 90 Salehurst Rd (1791-25) | 23 | 100.0% | 0 | - | READY |
| 3 Station Approach (1801-25) | 28 | 92.9% | 2 | - | READY |
| 26 Newton Rd (1803-25) | 28 | 92.9% | 2 | - | READY |
| Cayman House (1806-25) | 23 | 100.0% | 0 | - | READY |
| Outhouse (1809-25) | 275 | 100.0% | 0 | - | READY |
| 42 Lowther Hill (1816-25) | 96 | 100.0% | 0 | - | READY |
| 2 Olympic (1819-25) | 148 | 100.0% | 0 | exif_vs_pathdate_conflict | NEEDS-RULE |
| 3 Pancras Square (1831-25) | 16 | 100.0% | 0 | - | READY |
| Clifton Hill (1837-25) | 30 | 100.0% | 0 | - | READY |
| NW6 7PE area (unnamed site) (1841-26) [synthetic label] | 1 | 100.0% | 0 | - | READY |
| 1847-26 8 Rheidol Terrace N1 8NT (1847-26) | 1 | 100.0% | 0 | - | READY |
| 77 spencer park ave cv5 6de (1848-26) | 28 | 100.0% | 0 | - | READY |
| Rathbone Market, Canning Town (1851-26) | 21 | 100.0% | 0 | - | READY |
| 35 Wrentham Ave (1855-26) | 39 | 97.4% | 1 | - | READY |
| 45 Cornwall (1856-26) | 41 | 97.6% | 1 | - | READY |
| 166 New Bond St (1857-26) | 30 | 100.0% | 0 | - | READY |
| 5 Currie Hill Close (1858-26) | 26 | 100.0% | 0 | - | READY |
| Cumberland Rd (1859-26) | 12 | 100.0% | 0 | - | READY |
| 3 Fleet St (1860-26) | 45 | 95.6% | 2 | - | READY |
| 14 Alan Road, London, SW19 7PT (1864-26) | 16 | 100.0% | 0 | - | READY |
| 261 Railton Rd (1867-26) | 11 | 100.0% | 0 | - | READY |
| TW9 4HP (1869-25) | 1 | 100.0% | 0 | - | READY |
| Best Reception (1871-26) | 78 | 100.0% | 0 | - | READY |
| N1 9LL area (unnamed site) (1879-26) [synthetic label] | 1 | 100.0% | 0 | - | READY |
| WC1A 2QR area (contact: InMidTown) (197-13) [synthetic label] | 3 | 100.0% | 0 | - | READY |
| GU9 7JR area (contact: Richard Hilson) (206-13) [synthetic label] | 3 | 100.0% | 0 | - | READY |
| SE10 9EY area (contact: Rosie Sotillo) (207-13) [synthetic label] | 12 | 91.7% | 1 | - | READY |
| SW15 4JY area (contact: Paul Goodwin) (232-13) [synthetic label] | 16 | 100.0% | 0 | - | READY |
| GU24 0AJ area (contact: Jamie East) (271-14) [synthetic label] | 3 | 100.0% | 0 | - | READY |
| N16 5UG area (contact: EBCBuild) (285-14) [synthetic label] | 6 | 100.0% | 0 | - | READY |
| 2 Olympic Mews (301-14) | 95 | 100.0% | 0 | - | READY |
| BN43 5LB area (contact name withheld) (333-14) [synthetic label] | 11 | 90.9% | 1 | - | READY |
| KT10 0AH (34-11) | 63 | 96.8% | 2 | - | READY |
| BN2 3RN area (contact: Jim Floyd) (340-14) [synthetic label] | 8 | 100.0% | 0 | - | READY |
| NW3 3EL area (contact: Derek Wood) (343-14) [synthetic label] | 2 | 100.0% | 0 | - | READY |
| W1D 4BA (38-11) | 14 | 100.0% | 0 | - | READY |
| SW6 4EQ (415-14) | 2 | 100.0% | 0 | - | READY |
| Hammersmith & Fulham LBHF (433-15) | 216 | 97.7% | 5 | - | READY |
| BN1 5FA (48-11) | 5 | 100.0% | 0 | - | READY |
| (unnamed -- no site name anywhere) (483-15) | 73 | 100.0% | 0 | - | READY |
| Heli Hangar (528-15) | 78 | 100.0% | 0 | - | READY |
| BN1 6NE area (contact: John and Clare Fothergill) (534-15) [synthetic label] | 12 | 100.0% | 0 | - | READY |
| Cherryfield Dr (556-15) | 115 | 98.3% | 2 | - | READY |
| SE5 8BS area (unnamed site) (559-15) [synthetic label] | 9 | 100.0% | 0 | - | READY |
| W1U 6AG area (contact: Christian Science Office) (564-15) [synthetic label] | 1 | 100.0% | 0 | - | READY |
| 18 Cricketfield Rd (579-15) | 83 | 98.8% | 1 | - | READY |
| SE6 1XP area (contact: Nicola Simpson) (580-15) [synthetic label] | 13 | 100.0% | 0 | - | READY |
| SW1P 2LX area (unnamed site) (619-16) [synthetic label] | 8 | 100.0% | 0 | - | READY |
| Hadleigh (62-12) | 68 | 100.0% | 0 | - | READY |
| MK17 9EW area (contact: Melanie Paul) (636-16) [synthetic label] | 48 | 95.8% | 2 | - | READY |
| BN2 7BG area (contact: John Davies) (649-16) [synthetic label] | 9 | 100.0% | 0 | - | READY |
| 1 Litten Pl (651-16) | 51 | 100.0% | 0 | - | READY |
| Basuto Road (67-12) | 98 | 98.0% | 2 | exif_vs_pathdate_conflict | NEEDS-RULE |
| 4 Olympic Mews (673-16) | 41 | 100.0% | 0 | - | READY |
| SE15 5AT area (contact: Daniel Jacobs) (678-16) [synthetic label] | 20 | 95.0% | 1 | - | READY |
| BN7 1NH area (contact: Claire Ward and Saul Fowler) (704-16) [synthetic label] | 28 | 92.9% | 2 | - | READY |
| BN1 3HF area (contact: Brian Morris) (713-16) [synthetic label] | 2 | 100.0% | 0 | - | READY |
| 3 Olympic Mews (735-16) | 53 | 94.3% | 3 | - | READY |
| W6 0AJ area (contact: Catherine Jeanperrin) (738-16) [synthetic label] | 46 | 93.5% | 3 | - | READY |
| Materials Advance 56 Belsize Ave NW3 4AA (75-12) | 24 | 91.7% | 2 | - | READY |
| BN2 5RF area (contact: Lynda Pickworth) (757-15) [synthetic label] | 14 | 92.9% | 1 | - | READY |
| TN4 9PH area (contact: Algonquin Homes) (759-17) [synthetic label] | 34 | 97.1% | 1 | - | READY |
| 3 Stocklands Close Will Faas (760-17) | 101 | 98.0% | 2 | - | READY |
| BS1 6TJ area (unnamed site) (762-17) [synthetic label] | 10 | 100.0% | 0 | - | READY |
| TN5 6DB area (unnamed site) (763-17) [synthetic label] | 34 | 88.2% | 4 | - | READY |
| LEMO UK Ltd Worthing (777-17) | 48 | 97.9% | 1 | - | READY |
| 21 Riverside (788-17) | 38 | 81.6% | 7 | - | READY |
| GL7 5BT area (contact: Luke Carroll) (799-17) [synthetic label] | 8 | 100.0% | 0 | - | READY |
| SE22 0SD (80-12) | 20 | 100.0% | 0 | - | READY |
| TN13 2LL area (contact: Tom Hoppe) (804-17) [synthetic label] | 21 | 100.0% | 0 | - | READY |
| TN31 7SA area (contact: Mr & Mrs Egan) (810-17) [synthetic label] | 49 | 89.8% | 5 | - | READY |
| SE15 5DB area (contact: Clare Walker) (821-17) [synthetic label] | 3 | 66.7% | 1 | low_exif_coverage | NEEDS-RULE |
| BN1 6HJ area (contact: Charles Jackson) (831-17) [synthetic label] | 44 | 79.5% | 9 | low_exif_coverage | NEEDS-RULE |
| N1 4HL area (contact: Bronwen Manby) (843-18) [synthetic label] | 6 | 50.0% | 3 | low_exif_coverage | NEEDS-RULE |
| BN41 1DH area (contact: Millimetre Ltd) (848-18) [synthetic label] | 3 | 100.0% | 0 | - | READY |
| RH16 1UX area (contact: Richard Lipscombe) (866-18) [synthetic label] | 3 | 100.0% | 0 | - | READY |
| SE12 8LQ area (contact: Dominic Duncan) (872-18) [synthetic label] | 9 | 100.0% | 0 | - | READY |
| HP4 2DW area (contact: Lucy Glasser) (889-18) [synthetic label] | 34 | 97.1% | 1 | - | READY |
| N4 1AY area (contact: Kerri Nolan) (897-18) [synthetic label] | 4 | 100.0% | 0 | - | READY |
| BN2 1FF area (contact: Tony Marcello) (911-18) [synthetic label] | 17 | 94.1% | 1 | - | READY |
| E5 8NS (913-18) | 10 | 100.0% | 0 | - | READY |
| N4 4RB area (contact: Beth MacInnes) (916-18) [synthetic label] | 4 | 100.0% | 0 | - | READY |
| near Old Street (930-18) | 58 | 100.0% | 0 | - | READY |
| NW6 4PL area (contact: Sapphire IH) (939-18) [synthetic label] | 6 | 100.0% | 0 | - | READY |
| Velo Café, Brighton (94-12) | 168 | 97.6% | 4 | - | READY |
| BS22 6EX area (unnamed site) (943-18) [synthetic label] | 24 | 100.0% | 0 | - | READY |
| NW6 3DY area (contact: Richard Petit) (949-18) [synthetic label] | 5 | 80.0% | 1 | - | READY |
| SW2 4NX area (contact: Debbie Salmon) (956-18) [synthetic label] | 9 | 88.9% | 1 | - | READY |
| SW14 8QY area (contact: Angharad Bryn Jones) (958-18) [synthetic label] | 17 | 94.1% | 1 | - | READY |
| 13 St Davids Rd Chris Rule (970-19) | 99 | 100.0% | 0 | - | READY |
| N3 2EJ area (contact: Daniel & Liz Preter) (976-19) [synthetic label] | 9 | 88.9% | 1 | - | READY |
| BN3 8AJ area (unnamed site) (977-19) [synthetic label] | 1 | 100.0% | 0 | - | READY |
| HP5 2XT area (unnamed site) (992-19) [synthetic label] | 43 | 100.0% | 0 | exif_vs_pathdate_conflict | NEEDS-RULE |
| 55 Ainsworth Ave (996-19) | 63 | 96.8% | 2 | - | READY |

## NEEDS-RULE roofs -- proposed fallback ordering rules (PROPOSAL ONLY, not built)

### BN44 3PU area (contact: Matthew Wintersgill) (121-12) [synthetic label]

- 3 photos, 66.7% usable EXIF, flags: low_exif_coverage
- Proposed rule: Partial EXIF coverage (67%). Propose: use EXIF where present; for photos flagged no_exif_missing_on_disk or exif_unreadable, interpolate their position using path-date binned against the EXIF-dated photos from the same folder-date group, tie-broken by filename numeric sequence.

### 32 Nicosia Rd (1340-21)

- 54 photos, 94.4% usable EXIF, flags: exif_vs_pathdate_conflict
- Proposed rule: EXIF and path-date disagree by >180 days on 1 photo(s) (the known album/EXIF year-drift pattern, generalised to path-date). Propose: trust EXIF as capture-truth over path-date (path-date reflects the import/export folder the photo landed in, not when it was taken); only fall back to path-date for a photo when its own EXIF is missing.

### GRA sub-site variant of 1343-21, address=St Luke's Gardens (toilet building next to the playground/play area), Cale Stre (1343-21-STL)

- 52 photos, 96.2% usable EXIF, flags: exif_vs_pathdate_conflict
- Proposed rule: EXIF and path-date disagree by >180 days on 1 photo(s) (the known album/EXIF year-drift pattern, generalised to path-date). Propose: trust EXIF as capture-truth over path-date (path-date reflects the import/export folder the photo landed in, not when it was taken); only fall back to path-date for a photo when its own EXIF is missing.

### Flora Gardens (misfiled 2016 photos; own ref pending) (1641-23)

- 75 photos, 100.0% usable EXIF, flags: exif_vs_pathdate_conflict
- Proposed rule: EXIF and path-date disagree by >180 days on 1 photo(s) (the known album/EXIF year-drift pattern, generalised to path-date). Propose: trust EXIF as capture-truth over path-date (path-date reflects the import/export folder the photo landed in, not when it was taken); only fall back to path-date for a photo when its own EXIF is missing.

### 2 Olympic (1819-25)

- 148 photos, 100.0% usable EXIF, flags: exif_vs_pathdate_conflict
- Proposed rule: EXIF and path-date disagree by >180 days on 1 photo(s) (the known album/EXIF year-drift pattern, generalised to path-date). Propose: trust EXIF as capture-truth over path-date (path-date reflects the import/export folder the photo landed in, not when it was taken); only fall back to path-date for a photo when its own EXIF is missing.

### Basuto Road (67-12)

- 98 photos, 98.0% usable EXIF, flags: exif_vs_pathdate_conflict
- Proposed rule: EXIF and path-date disagree by >180 days on 2 photo(s) (the known album/EXIF year-drift pattern, generalised to path-date). Propose: trust EXIF as capture-truth over path-date (path-date reflects the import/export folder the photo landed in, not when it was taken); only fall back to path-date for a photo when its own EXIF is missing.

### SE15 5DB area (contact: Clare Walker) (821-17) [synthetic label]

- 3 photos, 66.7% usable EXIF, flags: low_exif_coverage
- Proposed rule: Partial EXIF coverage (67%). Propose: use EXIF where present; for photos flagged no_exif_missing_on_disk or exif_unreadable, interpolate their position using path-date binned against the EXIF-dated photos from the same folder-date group, tie-broken by filename numeric sequence.

### BN1 6HJ area (contact: Charles Jackson) (831-17) [synthetic label]

- 44 photos, 79.5% usable EXIF, flags: low_exif_coverage
- Proposed rule: Partial EXIF coverage (80%). Propose: use EXIF where present; for photos flagged no_exif_missing_on_disk or exif_unreadable, interpolate their position using path-date binned against the EXIF-dated photos from the same folder-date group, tie-broken by filename numeric sequence.

### N1 4HL area (contact: Bronwen Manby) (843-18) [synthetic label]

- 6 photos, 50.0% usable EXIF, flags: low_exif_coverage
- Proposed rule: Partial EXIF coverage (50%). Propose: use EXIF where present; for photos flagged no_exif_missing_on_disk or exif_unreadable, interpolate their position using path-date binned against the EXIF-dated photos from the same folder-date group, tie-broken by filename numeric sequence.

### HP5 2XT area (unnamed site) (992-19) [synthetic label]

- 43 photos, 100.0% usable EXIF, flags: exif_vs_pathdate_conflict
- Proposed rule: EXIF and path-date disagree by >180 days on 1 photo(s) (the known album/EXIF year-drift pattern, generalised to path-date). Propose: trust EXIF as capture-truth over path-date (path-date reflects the import/export folder the photo landed in, not when it was taken); only fall back to path-date for a photo when its own EXIF is missing.


## ORCHESTRATOR CORRECTION (Fable verify pass, 2026-07-10 late) — the 7 "conflicts" are export artifacts, not date conflicts

Verified by query this turn (all 7 photo-level `exif_vs_pathdate_conflict*` rows pulled from
`grind/spineline_readiness.json`): **every one of the 7 conflict photos carries an "EXIF"
timestamp of 2026-06-25** — the day the iCloud export was generated (`icloud-export-2026-06`)
— against path-dates of 2018–2025. `mdls kMDItemContentCreationDate` is reading the file
stamp written at export time on files whose real EXIF is absent or unreadable, exactly the
same failure mode as the `photo_ledger_merged.jsonl` `ts` finding above.

Corrected fallback proposal (still PROPOSE-only, nothing implemented):
- Any EXIF timestamp falling in the export window (2026-06-24..27) is an EXPORT ARTIFACT →
  treat as missing EXIF, use path-date. Do NOT trust EXIF over path-date in this case —
  the audit's original ">180 days → trust EXIF" rule would have mis-dated all 7.
- Consequence if adopted: the 6 conflict-flagged roofs (1340-21, 1343-21-STL, 1641-23,
  1819-25, 67-12, 992-19) reclassify from NEEDS-RULE to READY-with-rule; the remaining
  genuine NEEDS-RULE set is the 4 low-EXIF-coverage roofs (121-12, 821-17, 831-17, 843-18).
- F3 still does not start until Lee has seen this file (unchanged gate).
