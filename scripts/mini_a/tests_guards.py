#!/usr/bin/env python3
"""
tests_guards.py -- breach tests for guards.py (F1 spec Item B.4).
Runnable standalone on Mini A: `python3 tests_guards.py`.

Verifies each guard makes its breach IMPOSSIBLE, not merely documented-against:
  1. Free-text / model-labelled "caption" attempt -> Caption() raises.
  2. Species name without a real RefImage -> render_species_name() refuses.
  3. counts_footer() with counts.py absent -> renders failure text, never a number.
  4. A real rebuild (build_closeup_retest_sheet.py) still renders with guards in,
     with the footer block present and, since species names ARE present,
     ref-image slots present too.

Exits non-zero on any failure so this can gate a build.
"""
import os
import subprocess
import sys
import traceback

ROOT = os.path.expanduser("~/image-plane")
sys.path.insert(0, ROOT)
import guards  # noqa: E402


PASS = []
FAIL = []


def check(name, fn):
    try:
        fn()
        PASS.append(name)
        print("PASS:", name)
    except AssertionError as e:
        FAIL.append((name, str(e)))
        print("FAIL:", name, "--", e)
    except Exception as e:
        FAIL.append((name, "unexpected exception: %r" % e))
        print("FAIL:", name, "-- unexpected exception:", repr(e))
        traceback.print_exc()


# --------------------------------------------------------------------------
# 1. D3 -- free-text / model-source caption attempt must raise
# --------------------------------------------------------------------------

def test_caption_rejects_free_text_source():
    for bad_source in ("model", "qwen", "free", "vision", "", None, 42, ["lee_voice"]):
        raised = False
        try:
            guards.Caption("some description text", bad_source)
        except guards.CaptionSourceError:
            raised = True
        assert raised, "Caption(text, %r) did not raise CaptionSourceError" % (bad_source,)


def test_caption_accepts_only_ground_truth_enum():
    # These must NOT raise -- they're the closed set of legitimate sources.
    for good in (guards.CaptionSource.LEE_VOICE, guards.CaptionSource.GRA,
                 guards.CaptionSource.GROUND_TRUTH, guards.CaptionSource.NONE,
                 "lee_voice", "gra", "ground_truth", "none"):
        c = guards.Caption("text", good)
        assert isinstance(c.source, guards.CaptionSource)


def test_caption_empty_is_valid_and_renders_nothing():
    c = guards.Caption("", guards.CaptionSource.NONE)
    assert c.render_html() == "", "empty/NONE caption must render nothing, got %r" % c.render_html()
    c2 = guards.Caption("   ", guards.CaptionSource.LEE_VOICE)
    assert c2.render_html() == "", "whitespace-only caption must render nothing"


def test_caption_lee_voice_renders_labelled_block():
    c = guards.Caption("Sedum roof, dieback observed.", guards.CaptionSource.LEE_VOICE)
    out = c.render_html()
    assert "caption-lee_voice" in out, "expected a source-labelled caption class, got: %s" % out
    assert "Sedum roof, dieback observed." in out


# --------------------------------------------------------------------------
# 2. D4 -- species name without a real RefImage must be refused
# --------------------------------------------------------------------------

def test_render_species_name_refuses_non_refimage():
    for bogus in ("Sedum acre", None, 123, {"species_name": "Sedum acre", "image_path": None}):
        raised = False
        try:
            guards.render_species_name("Sedum acre", bogus)
        except guards.RefImageRequiredError:
            raised = True
        assert raised, "render_species_name() did not refuse a non-RefImage arg: %r" % (bogus,)


def test_render_species_name_refuses_mismatched_refimage():
    ref_for_other_species = guards.species_ref("Buddleja davidii")
    raised = False
    try:
        guards.render_species_name("Sedum acre", ref_for_other_species)
    except guards.RefImageRequiredError:
        raised = True
    assert raised, "render_species_name() accepted a RefImage for a different species name"


def test_unknown_species_gets_loud_placeholder_and_is_logged():
    needing_path = guards.SPECIES_NEEDING_EXEMPLAR_PATH
    before = []
    if os.path.exists(needing_path):
        import json
        before = json.load(open(needing_path))
    marker_name = "Zzz Test Species Never Seeded 20260710"
    ref = guards.species_ref(marker_name)
    assert ref.placeholder is True, "unseeded species must come back as a placeholder RefImage"
    out = guards.render_species_name(marker_name, ref)
    assert "NO REFERENCE IMAGE" in out, "placeholder markup must be loud, got: %s" % out
    import json
    after = json.load(open(needing_path))
    names_after = {row["name"] for row in after}
    assert marker_name in names_after, "unknown species name must be logged to species_needing_exemplar.json"
    assert len(after) == len(before) or marker_name not in {r["name"] for r in before}, "dedup check setup sane"
    # re-request must not duplicate the entry
    guards.species_ref(marker_name)
    after2 = json.load(open(needing_path))
    count_marker = sum(1 for r in after2 if r["name"] == marker_name)
    assert count_marker == 1, "species_needing_exemplar.json must dedupe by name, found %d entries" % count_marker


def test_seeded_species_renders_real_ref_image():
    ref = guards.species_ref("sycamore")
    assert ref.placeholder is False, "sycamore should be seeded with a real exemplar image"
    out = guards.render_species_name("sycamore", ref)
    assert "ref-thumb" in out, "seeded species must render an <img class=ref-thumb>, got: %s" % out
    assert "NO REFERENCE IMAGE" not in out


# --------------------------------------------------------------------------
# 3. D2 -- counts.py absent must render failure text, never a number
# --------------------------------------------------------------------------

def test_counts_footer_absent_script_renders_failure_text():
    fake_path = "/tmp/definitely-does-not-exist-counts-py-20260710/counts.py"
    assert not os.path.exists(fake_path)
    out = guards.counts_footer(counts_script=fake_path)
    assert "COUNTS UNAVAILABLE" in out, "expected visible failure text, got: %s" % out
    assert "counts-footer-error" in out
    # must not contain what looks like a real cached count sneaking through
    assert "keeps" not in out.lower() and "allocated" not in out.lower()


def test_counts_footer_broken_script_renders_failure_text_not_a_number():
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("import sys; sys.exit(3)\n")
        broken_path = f.name
    try:
        out = guards.counts_footer(counts_script=broken_path)
        assert "COUNTS UNAVAILABLE" in out, "non-zero-exit counts.py must still fail loudly, got: %s" % out
    finally:
        os.unlink(broken_path)


# --------------------------------------------------------------------------
# 4. Rebuild an existing real sheet -- proves output still renders with guards in
# --------------------------------------------------------------------------

def test_rebuild_closeup_retest_sheet_renders_with_guards():
    script = os.path.join(ROOT, "build_closeup_retest_sheet.py")
    out_path = os.path.join(ROOT, "grind/site_view/closeup-retest-r1.html")
    proc = subprocess.run(["python3", script], capture_output=True, text=True, timeout=180)
    assert proc.returncode == 0, "build_closeup_retest_sheet.py failed: %s" % proc.stderr[-2000:]
    assert os.path.exists(out_path), "expected output HTML at %s" % out_path
    html_out = open(out_path).read()
    assert "counts-footer" in html_out, "rebuilt sheet is missing the counts_footer block"
    assert "species-ref" in html_out, "rebuilt sheet has species names but no species-ref slot"
    # sanity: real content still there
    assert "Close-up plant-ID retest" in html_out


def main():
    check("caption_rejects_free_text_source", test_caption_rejects_free_text_source)
    check("caption_accepts_only_ground_truth_enum", test_caption_accepts_only_ground_truth_enum)
    check("caption_empty_is_valid_and_renders_nothing", test_caption_empty_is_valid_and_renders_nothing)
    check("caption_lee_voice_renders_labelled_block", test_caption_lee_voice_renders_labelled_block)
    check("render_species_name_refuses_non_refimage", test_render_species_name_refuses_non_refimage)
    check("render_species_name_refuses_mismatched_refimage", test_render_species_name_refuses_mismatched_refimage)
    check("unknown_species_gets_loud_placeholder_and_is_logged", test_unknown_species_gets_loud_placeholder_and_is_logged)
    check("seeded_species_renders_real_ref_image", test_seeded_species_renders_real_ref_image)
    check("counts_footer_absent_script_renders_failure_text", test_counts_footer_absent_script_renders_failure_text)
    check("counts_footer_broken_script_renders_failure_text_not_a_number", test_counts_footer_broken_script_renders_failure_text_not_a_number)
    check("rebuild_closeup_retest_sheet_renders_with_guards", test_rebuild_closeup_retest_sheet_renders_with_guards)

    print()
    print("=" * 60)
    print("PASSED: %d  FAILED: %d" % (len(PASS), len(FAIL)))
    if FAIL:
        print("FAILURES:")
        for name, msg in FAIL:
            print("  -", name, ":", msg)
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
