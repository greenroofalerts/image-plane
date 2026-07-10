#!/usr/bin/env python3
"""
guards.py -- F1 render guards for the image-plane sheet/page builders (LEE-411).

Spec: docs/F1-GUARDS-SPEC-2026-07-10.md, Item B. Enforcement-by-construction: each
guard makes a breach IMPOSSIBLE at the render layer, not merely documented-against.

Three guards:
  1. Caption / caption()        -- D3: a caption may only carry ground-truth text.
                                    Model/free text can NEVER reach a caption slot;
                                    the Caption constructor raises on any source that
                                    isn't a recognised ground-truth enum member.
  2. RefImage / species_ref() /
     render_species_name()      -- D4: every species name rendered on a sheet must
                                    go through a template helper that REQUIRES a
                                    RefImage argument. No exemplar -> loud placeholder
                                    + logged to grind/species_needing_exemplar.json.
  3. counts_footer()            -- D2: corpus counts are read from counts.py --json
                                    AT RENDER TIME. Never a cached/hardcoded number.
                                    counts.py absent/failing -> visible failure text.

Read-only on: knowledge_notes.jsonl, grind/gra_stories.json, grind/allocation_v2.jsonl,
grind/site_names.json, grind/species_exemplars.json.
Owns (read+append): grind/species_needing_exemplar.json.

Python 3.9 -- no match statements, no PEP 604 unions.
"""
import datetime
import enum
import html
import json
import os
import re
import shutil
import subprocess

ROOT = os.path.expanduser("~/image-plane")
GRIND = os.path.join(ROOT, "grind")

KNOWLEDGE_NOTES_PATH = os.path.join(ROOT, "knowledge_notes.jsonl")
GRA_STORIES_PATH = os.path.join(GRIND, "gra_stories.json")
GROUND_TRUTH_GLOB_DIR = GRIND  # files matching *ground*truth*.json live here, if any
SPECIES_EXEMPLARS_PATH = os.path.join(GRIND, "species_exemplars.json")
SPECIES_NEEDING_EXEMPLAR_PATH = os.path.join(GRIND, "species_needing_exemplar.json")
COUNTS_SCRIPT_DEFAULT = os.path.join(ROOT, "counts.py")


def _now_iso():
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _get(obj, key, default=None):
    """Duck-typed field access: dict.get, or getattr for object-like rows."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


# --------------------------------------------------------------------------
# D3 -- Caption guard
# --------------------------------------------------------------------------

class CaptionSourceError(ValueError):
    """Raised when a Caption is constructed with anything other than a
    recognised ground-truth source. This is the structural block that makes
    'free/model text in the caption slot' impossible."""


class CaptionSource(enum.Enum):
    LEE_VOICE = "lee_voice"          # knowledge_notes.jsonl, source: lee_voice
    GRA = "gra"                      # grind/gra_stories.json Lee-authored fields
    GROUND_TRUTH = "ground_truth"    # Lee's ground-truth JSONs (spine-capture / role-label format)
    NONE = "none"                    # explicit, valid "no ground truth found" state


_SOURCE_LABELS = {
    CaptionSource.LEE_VOICE: "Lee",
    CaptionSource.GRA: "GRA record",
    CaptionSource.GROUND_TRUTH: "ground truth",
    CaptionSource.NONE: "",
}


class Caption(object):
    """A caption that can ONLY carry ground-truth text.

    The constructor is the enforcement point: `source` must be a CaptionSource
    member (or its exact .value string). Anything else -- 'model', 'qwen',
    'free', a made-up string, an int, None -- raises CaptionSourceError.
    Empty text with source=NONE is valid and renders as no caption at all;
    it must never be back-filled with model text.
    """
    __slots__ = ("text", "source", "meta")

    def __init__(self, text, source, meta=None):
        if isinstance(source, CaptionSource):
            resolved = source
        elif isinstance(source, str):
            try:
                resolved = CaptionSource(source)
            except ValueError:
                raise CaptionSourceError(
                    "Caption source %r is not a ground-truth source. Allowed: %s. "
                    "Model/vision text must render in a separate labelled 'model' "
                    "block via the builder's own markup -- never through Caption()."
                    % (source, [m.value for m in CaptionSource])
                )
        else:
            raise CaptionSourceError(
                "Caption source must be a CaptionSource member or its string "
                "value, got %r (%s)" % (source, type(source).__name__)
            )
        self.source = resolved
        self.text = (text or "").strip()
        self.meta = meta or {}

    def render_html(self):
        """Empty or NONE-sourced captions render as nothing -- not a model fill."""
        if self.source is CaptionSource.NONE or not self.text:
            return ""
        label = _SOURCE_LABELS[self.source]
        css = "caption caption-%s" % self.source.value
        label_html = (
            "<span class='caption-label'>%s</span> " % html.escape(label)
            if label
            else ""
        )
        return "<div class='%s'>%s%s</div>" % (
            css,
            label_html,
            html.escape(self.text),
        )


_knowledge_by_path = None


def _load_knowledge_notes():
    global _knowledge_by_path
    if _knowledge_by_path is not None:
        return _knowledge_by_path
    idx = {}
    if os.path.exists(KNOWLEDGE_NOTES_PATH):
        with open(KNOWLEDGE_NOTES_PATH) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                p = row.get("path")
                note = row.get("note")
                # Only rows carrying an actual Lee note qualify as caption sources.
                if p and note and row.get("source") == "lee_voice":
                    # Keep the richest/most recent row per path (later rows in the
                    # file are later ingests; last write wins, same as the file's
                    # own convention elsewhere in this codebase).
                    idx[p] = row
    _knowledge_by_path = idx
    return idx


# GRA story "kind" -> the GRA field name it stands in for (per spec: last_actions_at_visit
# / last_condition_notes / last_recommendations, which are live Supabase `sites` columns not
# mirrored 1:1 in grind/gra_stories.json; these are the closest local kinds carrying Lee's own
# operator words. "alert_sent" is excluded -- that's automated cron text, not Lee's voice.)
_GRA_KIND_TO_FIELD = {
    "recommendation_update": "last_recommendations",
    "site_note": "last_condition_notes",
    "inspection": "last_condition_notes",
    "visit": "last_actions_at_visit",
}

_gra_by_job = None


def _load_gra_stories():
    global _gra_by_job
    if _gra_by_job is not None:
        return _gra_by_job
    idx = {}
    if os.path.exists(GRA_STORIES_PATH):
        try:
            data = json.load(open(GRA_STORIES_PATH))
        except Exception:
            data = {}
        for job_ref, rec in (data or {}).items():
            best = {}
            for story in rec.get("stories", []) or []:
                kind = story.get("kind")
                field = _GRA_KIND_TO_FIELD.get(kind)
                if not field:
                    continue
                prose = (story.get("prose") or "").strip()
                if not prose:
                    continue
                date = story.get("date") or ""
                prev = best.get(field)
                if prev is None or date >= prev[0]:
                    best[field] = (date, prose, kind)
            if best:
                idx[job_ref] = best
    _gra_by_job = idx
    return idx


_ground_truth_by_path = None


def _load_ground_truth_jsons():
    """Lee's ground-truth JSONs (role/label / spine-capture format). None found on
    Mini A at spec time (2026-07-10) -- glob is checked at call time so a future
    drop-in is picked up without a guards.py edit. Read-only, never written here."""
    global _ground_truth_by_path
    if _ground_truth_by_path is not None:
        return _ground_truth_by_path
    idx = {}
    import glob as _glob
    for fp in _glob.glob(os.path.join(GROUND_TRUTH_GLOB_DIR, "*ground*truth*.json")):
        try:
            data = json.load(open(fp))
        except Exception:
            continue
        rows = data if isinstance(data, list) else data.values()
        for row in rows:
            if not isinstance(row, dict):
                continue
            p = row.get("path")
            text = row.get("caption") or row.get("note") or row.get("label")
            if p and text:
                idx[p] = text
    _ground_truth_by_path = idx
    return idx


def caption(photo):
    """guards.caption(photo) -> Caption

    `photo` is a dict-like row with (at least) 'path' and/or 'job_ref'. Looks up
    ground truth in order: (1) a Lee-voice note on this exact photo path, (2) a
    ground-truth JSON on this exact photo path, (3) a GRA per-job field, in that
    priority (most specific to least specific). If none match, returns a valid,
    empty Caption(source=NONE) -- never a model fill.
    """
    path = _get(photo, "path")
    job_ref = _get(photo, "job_ref") or _get(photo, "job")

    if path:
        kn = _load_knowledge_notes().get(path)
        if kn:
            return Caption(kn.get("note"), CaptionSource.LEE_VOICE,
                            meta={"batch": kn.get("batch"), "n": kn.get("n")})

        gt_text = _load_ground_truth_jsons().get(path)
        if gt_text:
            return Caption(gt_text, CaptionSource.GROUND_TRUTH, meta={"path": path})

    if job_ref:
        gra_rec = _load_gra_stories().get(job_ref)
        if gra_rec:
            # Prefer condition notes, then recommendations, then actions-at-visit.
            for field in ("last_condition_notes", "last_recommendations", "last_actions_at_visit"):
                hit = gra_rec.get(field)
                if hit:
                    date, prose, kind = hit
                    return Caption(prose, CaptionSource.GRA,
                                   meta={"field": field, "date": date, "gra_kind": kind, "job_ref": job_ref})

    return Caption("", CaptionSource.NONE)


# --------------------------------------------------------------------------
# D4 -- species reference-image guard
# --------------------------------------------------------------------------

class RefImageRequiredError(TypeError):
    """Raised when a caller tries to render a species name without going
    through species_ref() first -- i.e. without a real RefImage."""


def _norm(s):
    return re.sub(r"\s+", " ", (s or "").strip().lower())


_exemplars = None


def _load_exemplars():
    global _exemplars
    if _exemplars is not None:
        return _exemplars
    data = {}
    if os.path.exists(SPECIES_EXEMPLARS_PATH):
        try:
            data = json.load(open(SPECIES_EXEMPLARS_PATH))
        except Exception:
            data = {}
    _exemplars = data
    return data


def _match_exemplar_slug(name):
    """Return the exemplar slug matching `name` (by slug, common_name, latin, or
    alias -- case/space-insensitive, either-direction substring), or None."""
    n = _norm(name)
    if not n:
        return None
    exemplars = _load_exemplars()
    # exact slug match first
    for slug in exemplars:
        if _norm(slug) == n:
            return slug
    # alias / common / latin match
    for slug, rec in exemplars.items():
        candidates = [rec.get("common_name"), rec.get("latin")] + list(rec.get("aliases") or [])
        for c in candidates:
            cn = _norm(c)
            if not cn:
                continue
            if cn == n or cn in n or n in cn:
                return slug
    return None


def _append_needing_exemplar(name, reason):
    if not os.path.exists(SPECIES_NEEDING_EXEMPLAR_PATH):
        existing = []
    else:
        try:
            existing = json.load(open(SPECIES_NEEDING_EXEMPLAR_PATH))
        except Exception:
            existing = []
    key = _norm(name)
    for row in existing:
        if _norm(row.get("name", "")) == key:
            return  # already queued, dedup
    existing.append({"name": name, "reason": reason, "added_at": _now_iso()})
    with open(SPECIES_NEEDING_EXEMPLAR_PATH, "w") as f:
        json.dump(existing, f, indent=1)


class RefImage(object):
    """A resolved (or explicitly missing) reference image for a species name.
    Only species_ref() may construct one with placeholder=False -- builders
    must not fabricate a RefImage by hand."""
    __slots__ = ("species_name", "slug", "image_path", "placeholder")

    def __init__(self, species_name, slug=None, image_path=None):
        self.species_name = species_name
        self.slug = slug
        self.image_path = image_path
        self.placeholder = image_path is None


def species_ref(name):
    """guards.species_ref(name) -> RefImage

    Looks up `name` in grind/species_exemplars.json. If a seeded exemplar
    exists AND its image file is still present on disk, returns a live
    RefImage. Otherwise returns a placeholder RefImage AND appends the name
    to grind/species_needing_exemplar.json (deduped) -- this happens for
    ANY unresolved name, known-vocab or not: unknown name -> placeholder,
    never silent.
    """
    slug = _match_exemplar_slug(name)
    if slug:
        rec = _load_exemplars()[slug]
        img = rec.get("image_path")
        if img and os.path.exists(img):
            return RefImage(name, slug=slug, image_path=img)
        if img:
            reason = "exemplar image for %r no longer on disk (%s)" % (slug, img)
        else:
            reason = "%r is in species_exemplars.json but has no photo exemplar yet" % slug
        _append_needing_exemplar(name, reason)
        return RefImage(name, slug=slug, image_path=None)

    _append_needing_exemplar(name, "no exemplar in species_exemplars.json")
    return RefImage(name, slug=None, image_path=None)


def render_species_name(name, ref_image, dest_dir=None, dest_rel_prefix="ref_images"):
    """The template helper that renders a species name. STRUCTURALLY requires
    a RefImage (raises RefImageRequiredError on anything else) -- this is what
    makes 'a builder hand-rolls a <span class=species> without a ref image'
    impossible. If ref_image doesn't match `name`, also raises (prevents a
    stale/swapped RefImage being passed through).

    dest_dir, if given, is the sheet's own served-photo directory; the
    exemplar image is copied there (once) so it's servable alongside the
    sheet, and the returned markup points at the copy.
    """
    if not isinstance(ref_image, RefImage):
        raise RefImageRequiredError(
            "render_species_name() requires a RefImage from guards.species_ref() "
            "-- got %r (%s). Call guards.species_ref(name) first." % (ref_image, type(ref_image).__name__)
        )
    if ref_image.species_name != name:
        raise RefImageRequiredError(
            "RefImage is for %r, not %r -- fetch a fresh RefImage per species name, "
            "don't reuse one across different names." % (ref_image.species_name, name)
        )

    name_html = "<span class='species-name'>%s</span>" % html.escape(name)

    if ref_image.placeholder:
        return (
            "<div class='species-ref species-ref-missing'>"
            "%s<div class='ref-missing-badge'>NO REFERENCE IMAGE</div>"
            "</div>" % name_html
        )

    src = ref_image.image_path
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)
        ext = os.path.splitext(src)[1].lower() or ".jpg"
        dest_name = (ref_image.slug or _norm(name).replace(" ", "_")) + ext
        dest_path = os.path.join(dest_dir, dest_name)
        if not os.path.exists(dest_path):
            try:
                shutil.copy2(src, dest_path)
            except Exception:
                # copy failure degrades to placeholder rather than a broken <img>
                return (
                    "<div class='species-ref species-ref-missing'>"
                    "%s<div class='ref-missing-badge'>NO REFERENCE IMAGE (copy failed)</div>"
                    "</div>" % name_html
                )
        img_src = os.path.join(dest_rel_prefix, dest_name)
    else:
        img_src = src

    return (
        "<div class='species-ref'>"
        "<img class='ref-thumb' src='%s' alt='Reference: %s' loading='lazy'>"
        "%s"
        "</div>" % (html.escape(img_src), html.escape(name), name_html)
    )


# --------------------------------------------------------------------------
# D2 -- counts footer
# --------------------------------------------------------------------------

def _footer_html(inner, ok):
    cls = "counts-footer" if ok else "counts-footer counts-footer-error"
    return "<div class='%s'>%s</div>" % (cls, inner)


def _failure_footer(message):
    return _footer_html(
        "<b>COUNTS UNAVAILABLE</b> &mdash; %s. Never showing a cached number." % html.escape(message),
        ok=False,
    )


def counts_footer(counts_script=None, timeout=30):
    """guards.counts_footer() -> HTML string.

    Calls `python3 counts.py --json` AT RENDER TIME (i.e. when the builder runs,
    not baked into the template beforehand). counts.py is Item A's interface --
    coded against `--json` output even while Item A is in flight. On ANY
    failure (missing file, non-zero exit, bad JSON) this renders visible
    failure text -- it NEVER falls back to a hardcoded/cached number.
    """
    script = counts_script or COUNTS_SCRIPT_DEFAULT

    if not os.path.exists(script):
        return _failure_footer("counts.py not found at %s" % script)

    try:
        proc = subprocess.run(
            ["python3", script, "--json"],
            capture_output=True, text=True, timeout=timeout,
        )
    except Exception as e:
        return _failure_footer("counts.py could not be run: %s" % e)

    if proc.returncode != 0:
        return _failure_footer(
            "counts.py exited %d: %s" % (proc.returncode, (proc.stderr or "").strip()[:300])
        )

    try:
        data = json.loads(proc.stdout)
    except Exception as e:
        return _failure_footer("counts.py did not return valid JSON: %s" % e)

    return _footer_html(_render_counts_data(data), ok=True)


def _render_counts_data(data):
    """Flexible rendering: Item A's exact schema carries counted_by/counted_at
    per field (per spec); render whatever shape shows up rather than assuming
    field names that might drift while Item A is still in flight."""
    if not isinstance(data, dict):
        return "Counts: %s" % html.escape(json.dumps(data))

    lines = []
    top_ts = data.get("counted_at") or data.get("generated_at")
    for key, val in data.items():
        if key in ("counted_at", "generated_at"):
            continue
        if isinstance(val, dict) and ("value" in val or "count" in val):
            v = val.get("value", val.get("count"))
            by = val.get("counted_by")
            at = val.get("counted_at")
            bits = ["<b>%s</b>: %s" % (html.escape(str(key)), html.escape(str(v)))]
            if by:
                bits.append("<span class='counted-by'>Counted by: %s</span>" % html.escape(str(by)))
            if at:
                bits.append("<span class='counted-at'>%s</span>" % html.escape(str(at)))
            lines.append(" &middot; ".join(bits))
        else:
            lines.append("<b>%s</b>: %s" % (html.escape(str(key)), html.escape(str(val))))

    if top_ts:
        lines.append("<span class='counted-at'>as of %s</span>" % html.escape(str(top_ts)))

    return "<br>".join(lines) if lines else "counts.py returned no fields"
