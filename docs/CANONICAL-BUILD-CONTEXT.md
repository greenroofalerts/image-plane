# Current execution context — phone monitor slice, 11 September 2026

This branch captures the existing Mini A monitor and its tests. It does not replace
or bootstrap the Image Plane application, intake, classifier or Identity Ladder.
The current user instruction authorises making that existing monitor usable privately
on a phone while preserving concurrent Image Plane and Memory Spine processing.
This paragraph records implementation scope; it is not a new business ruling.

For this narrow slice, read and apply:

1. The current user continuation and phone-monitor instruction, with the maintained
   State of Play `docs/GREEN-ROOF-SPINE-BUILD-BRIEF.md` on `main` (phone-visible
   execution amendment). Preserve product ownership, originals and existing workers;
   report actual execution separately from instructions and configuration.
2. The current Mini A runtime documents under
   `incoming/worker/build-continuation-20260910/`: `CURRENT-STATUS.md` and
   `IMAGE-PLANE-AGENT-HANDOVER.md`; and `~/image-plane/docs/SCREENING-GATE-REPAIR-2026-09-10.md`
   plus `IMAGE-TEXT-REPAIR-2026-09-10.md`. These are operational contracts/checkpoints,
   not certification that the whole pipeline is complete.
3. The current `green-roof-image-plane` and `id-ladder` skills, machine `COMPASS.md`
   and `ASK-LEDGER.md`. Use the existing read-only records and source-scoped guards;
   no identity reassignment, inferred approval, species authority or customer send.
4. `docs/PHONE-MONITOR-2026-09-11.md` and the current dated section in
   `CURRENT_STATE.md` for this slice's actual source/runtime, verification and rollback.

The full-application manifest below is retained as history and broader context.
Its referenced root `CLAUDE.md` is absent from the inspected repository and Mini A
runtime; its prior `CURRENT_STATE.md` is July history and several older rules have
later corrections in the current skills. No missing file is claimed read. The narrow
monitor execution contract above supplies the current scope without inventing a
replacement application canon or treating a missing/stale instruction as business
authority. Full-application canonical reconciliation remains separate work.

---

# docs/CANONICAL-BUILD-CONTEXT.md — image-plane (LEE-411) canonical-docs manifest

**Status:** CANONICAL — staged 2026-07-10 late eve, ratified same night by Lee's "go in new window, handover".
**Owner:** Lee.

Standing rule (cross-repo, from the Glengarry manifest): every Lee-owned repo gets its own
manifest; a repo without one is a halt condition. This is image-plane's.

## Read order (required, in this exact order)

| # | Path | Type | One-line purpose |
|---|---|---|---|
| 1 | `CLAUDE.md` (repo root) | canonical | Local-only constraint (photo bytes never leave the machine), anti-amnesia block (allocation ALREADY SOLVED — source order, GRA=lookup-not-authority, boundary), GLM rules, working rules. |
| 2 | `CURRENT_STATE.md` | canonical | Single here's-where-things-stand pointer: corpus counts (via counts.py ONLY), map state, what's proven/live/blocked, next blocker. Update after every gate that changes proven/live/blocked/next. |
| 3 | `docs/product-control/ASK-LEDGER.md` | canonical | Lee's rulings, quoted and dated. Outranks every summary, report, and handover. |
| 4 | `BUILD-LESSONS-LEDGER.md` (repo root) | canonical (repo-local) | Image-plane standing build lessons (IP-L1…). Distinct from the external cross-repo ledger. |
| 5 | `docs/CANONICAL-BUILD-CONTEXT.md` | canonical (meta) | This file, read last in the manifest pass to re-verify the manifest itself. |

## External canonical (referenced, lives outside this repo)

| Path | Purpose |
|---|---|
| `~/.claude/rules/COMPASS.md` + `~/.claude/rules/ASK-LEDGER.md` | Machine law + machine-wide rulings. |
| `~/.claude/skills/green-roof-image-plane/SKILL.md` | The operational playbook: sources in priority order, established scripts, hard rules, guards, address-stores inventory pointer. |
| `~/processpnlv2/docs/BUILD-LESSONS-LEDGER.md` | Cross-repo lessons ledger (L001–Lnn); read iff a change touches a ledger-named pattern. |
| `~/glenross/docs/product-control/GLENROSS-ALLOCATION-SOURCE-AUDIT-2026-06-23.md` + `GLENROSS-SITE-FACT-HARVESTER-V3-2026-06-23.md` | The established job→site resolution method. Consult before ANY geocode/allocate/address work. |

## Historical evidence (NOT canonical first-read)

`docs/DELTA-IMAGE-PLANE-2026-07-10.md` and the `docs/F2-*.md` run logs are point-in-time
evidence; `CURRENT_STATE.md` supersedes them as state. The dated 2026-06-30 root docs
(END-USES, MOVE-1 spec, DELIVERY-MAP) carry the retired "~21.5k" figure — history only,
never quote counts from them (counts.py is the only number source).

## How to use / staleness / stop

Same as the Glengarry manifest: read 1–5 in order; if any canonical doc is missing, stale,
or contradictory, STOP and report; final reports MUST carry `Canonical docs read: [exact
list]` and `Binding rules from each: [one line per doc]`. `CURRENT_STATE.md` is stale if
its stamp predates the latest commit touching scripts/ or docs/ run logs. Adding/removing
canonical docs is a Lee decision — propose, never silently edit this list.
