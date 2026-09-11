# Existing Image Plane phone monitor — 11 September 2026

The existing Image Plane progress page is now reachable through the existing private
State of Play TLS transport:

https://macminibs-mac-mini.taild9fb8c.ts.net:8843/collection/progress

Use an enrolled mesh device and the existing private viewer login. No customer
publication, new photo worker, classifier, operational store or dashboard was created.
Mini A's separate mesh client remains NeedsLogin; authorised LAN SSH to Mini B was
used without changing that login state.

The page reads the current scope checkpoint, saved publication, phase ledgers and
screened photo records. It distinguishes running entry screening from held diagnostic
passes; successful result time from checkpoint time; worker-run checks from catalogue
items awaiting screening; newest screening decision from latest published photograph.
Held/excluded originals remain outside previews. The current catalogue remainder is
not a complete cloud-source total, and a completed pass is not a completed photograph.

It refreshes every 15 seconds. Missing responses become stale/unknown after one minute;
a live process without a fresh checkpoint is stalled after three minutes. Publication
staleness is separate. Existing original ProcessPnL styling and Image Plane guards
remain in place. The latest published photo uses the existing screened thumbnail
route and retains Lee words separately from machine proposals.

## Executed verification

- Ten focused status tests passed: distinct counts, stale process, stopped worker,
  stale publication, held-preview containment, successful timestamps not moved by
  later errors, unknown missing timestamps, error-only checkpoints, active-phase labels and removed
  diagnostic previews. Eleven existing surface guards passed.
- Actual browser checks at 320 and 390 CSS pixels had no horizontal overflow and
  loaded a real published thumbnail. A timed unattended refresh changed the displayed
  source timestamp. The stale indicator was exercised and recovered. Screenshots and
  private source receipts remain on Mini A.
- Mini B, an enrolled host, requested the exact HTTPS URL with system trust and
  hostname verification enabled: anonymous page/records 401; authenticated page/records
  200; the pre-existing Spine route 200. POST returned 405, an unmapped route 404,
  an excluded photograph 404, and a retained JPEG 200. No certificate bypass was used.
- The same Image Plane scope process continued producing new decisions during the
  repair. Only the existing HTTP reader and TLS transport were reloaded; collection,
  scope, JPEG, diagnostic, Recon, GRA and ProcessPnL processing workers were preserved.

Physical iPhone acceptance remains unverified. This proves the rendered browser,
private transport and live source connection; it does not complete source enumeration,
identity/event adjudication, failed diagnostic controls or the whole Image Plane.

## Runtime/source boundary and rollback

These two monitor files are captured from the newer Mini A continuation runtime at
`incoming/worker/runtime/continuation-20260910`. The upstream reader repair branch was
last updated 9 September; the actual 10–11 September runtime was newer. This branch
adds the monitor source and focused tests without replacing older tracked worker
files with a different runtime. It is not a full standalone runtime restoration pack.

The scoped monitor backup is under
`incoming/worker/backups/before-phone-monitor-1789150704/`. Restore only those two
files and reload the existing HTTP reader to roll back this page. The TLS transport
has its own private Mini B pre-route backup. Its existing bounded runner owns one
loopback-only SSH tunnel to the unchanged Mini A listener, using the already trusted
host identity. Viewer authentication is checked before forwarding any Image Plane
read, and credentials are not sent to the Image Plane upstream.

Instruction provenance: the repository's manifest references a missing `CLAUDE.md`
and its July status/rules contain historical material superseded by later instructions.
They were not silently replaced or claimed current. The explicit user continuation,
latest maintained brief, current runtime handover/status, current Image Plane skill,
Identity Ladder and machine rules governed this bounded work. The dated monitor-specific execution context in
`docs/CANONICAL-BUILD-CONTEXT.md` now records the applicable scope, current contracts
and missing-file fact; full-application canonical reconciliation is not claimed complete. No identity resolver or ruling writer was changed.
