"""Read-only corpus sweep for the Product Contract acceptance harness.

Runs ON Mini A against the live retained collection
(incoming/worker/collection/results.json). Prints one line per condition
probe. Never writes anything.
"""
import json, re, sys, collections

RESULTS = "/Users/macminia/image-plane/incoming/worker/collection/results.json"
REF = re.compile(r"(?<![\w-])\d{3,4}-\d{2}(?:-[A-Za-z]+)?(?![\w-])")


def dict_or_none(o):
    return o if isinstance(o, dict) else None


def main():
    d = json.load(open(RESULTS))
    print("records:", len(d))

    # C2: every job-assigned record carries >=2 ladder lanes or lee_answer
    meth = collections.Counter()
    bad_method = []
    for r in d:
        ident = dict_or_none(r.get("identity"))
        if not ident or not ident.get("job_ref"):
            continue
        job = dict_or_none(ident.get("job")) or {}
        ev = dict_or_none(job.get("evidence")) or {}
        m = ev.get("method") or ""
        lanes = [l for l in m.split("+") if l.startswith("lane")]
        if len(lanes) >= 2 or m == "lee_answer":
            meth["ok"] += 1
        else:
            meth["bad"] += 1
            bad_method.append((r["sha256"][:12], ident.get("job_ref"), m))
    print("C2 job-assigned:", sum(meth.values()), "tally:", dict(meth),
          "bad:", len(bad_method), bad_method[:5])

    # C3: album title carrying a job code vs assigned identity
    okc, viol = 0, []
    albums = collections.Counter()
    for r in d:
        ident = dict_or_none(r.get("identity")) or {}
        jr = ident.get("job_ref")
        for m in r.get("memberships") or []:
            if not isinstance(m, dict):
                continue
            t = m.get("album") or ""
            refs = REF.findall(t)
            if not refs:
                continue
            albums[t] += 1
            if jr == refs[0]:
                okc += 1
            else:
                job = dict_or_none(ident.get("job")) or {}
                ev = dict_or_none(job.get("evidence")) or {}
                viol.append((r["sha256"][:12], t, refs[0], jr, ev.get("method")))
    print("C3 album-ref rows:", okc + len(viol), "match:", okc, "differ:", len(viol))
    for v in viol[:12]:
        print("   ", v)

    # C6: billable-event classification
    ch, evst = collections.Counter(), collections.Counter()
    for r in d:
        e = dict_or_none(r.get("event"))
        if e:
            ch[e.get("chargeability")] += 1
            evst[e.get("state")] += 1
    print("C6 chargeability:", dict(ch))
    print("C6 event states:", dict(evst))

    # C7: keywords / component labels
    kw = collections.Counter()
    for r in d:
        k = dict_or_none(r.get("keywords"))
        if not k:
            continue
        for src in ("lee", "machine_proposals", "original_words"):
            v = k.get(src)
            if isinstance(v, list):
                for w in v:
                    kw[(src, str(w))] += 1
    print("C7 distinct terms:", len({w for (_, w) in kw}),
          "sample:", list(kw.items())[:8])

    # C4: evidence preserved for every job assignment
    noev = 0
    for r in d:
        ident = dict_or_none(r.get("identity"))
        if ident and ident.get("job_ref"):
            job = dict_or_none(ident.get("job"))
            if not (job and isinstance(job.get("evidence"), dict)):
                noev += 1
    print("C4 job rows w/o evidence dict:", noev)

    # C9: display formats
    fmt = collections.Counter(str(r.get("display_format")) for r in d)
    print("C9 display_format:", dict(fmt))


if __name__ == "__main__":
    main()
