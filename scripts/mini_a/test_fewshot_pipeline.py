#!/usr/bin/env python3
"""Model-free checks for the approved few-shot photo teaching work."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import build_fewshot_teaching as builder
import fewshot_contact_sheet as sheet
import fewshot_engine as engine
import fewshot_note_judge as judge


class FewshotPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.excluded = self.root / "excluded.jsonl"
        self.excluded.write_text('{"sha":"a"}\n{"sha256":"b"}\n')
        self.teaching = [
            {"teaching_id": "lee-review-20260801:photo-01", "job_ref": "1000-26", "source_path": "review-a.jpg", "source_sha256": "ra", "approved_summary": "roof edge", "reader_example_eligible": True},
            {"teaching_id": "lee-review-20260801:photo-02", "job_ref": "1000-26", "source_path": "review-a.jpg", "source_sha256": "other", "approved_summary": "repeat path", "reader_example_eligible": True},
            {"teaching_id": "lee-review-20260801:photo-03", "job_ref": "1000-26", "source_path": "second.jpg", "source_sha256": "ra", "approved_summary": "repeat hash", "reader_example_eligible": True},
            {"teaching_id": "lee-review-20260801:photo-04", "job_ref": "2000-26", "source_path": "review-b.jpg", "source_sha256": "rb", "approved_summary": "other roof", "reader_example_eligible": True},
        ]

    def tearDown(self):
        self.temp.cleanup()

    def make_photo(self, name, body=b"photo"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return path

    def complete_reviews(self):
        """Forty rows in the real approved-spine shape, each with a real file."""
        rows = []
        for number in range(1, 41):
            photo = self.make_photo(f"review-{number}.jpg", f"photo-{number}".encode())
            rows.append({
                "id": f"spine-{number}",
                "source": "image-plane-fewshot-review-20260801",
                "source_id": f"photo-{number:02d}",
                "extracted_fields": {
                    "record_type": "approved_photo_teaching",
                    "photo_number": number,
                    "photo_path": str(photo),
                    "job_ref": "1000-26",
                    "approved_summary": f"summary {number}",
                    "engine_labels": [],
                    "project": "image plane",
                    "work_bucket": "photo matching",
                },
            })
        return rows

    def test_00_runtime_annotations_are_deferred_for_python_39(self):
        self.assertEqual(engine.sha256_of.__annotations__["path"], "str | Path")
        self.assertEqual(judge.judge_one.__annotations__["return"], "dict | None")

    def test_01_excluded_loader_accepts_both_hash_fields(self):
        self.assertEqual(engine.load_excluded_shas(self.excluded), {"a", "b"})

    def test_02_excluded_photo_never_reaches_model(self):
        photo = self.make_photo("blocked.jpg")
        sha = engine.sha256_of(photo)
        with patch.object(engine, "label_photo") as label:
            row = engine.label_candidate(photo, {sha}, [], "[]", labeler=label)
        self.assertEqual(row["skip_reason"], "excluded")
        label.assert_not_called()

    def test_03_teaching_ids_are_distinct_and_exactly_forty(self):
        records = builder.build_teaching_records(self.complete_reviews(), set())
        self.assertEqual(len(records), 40)
        self.assertEqual(len({row["teaching_id"] for row in records}), 40)

    def test_04_repeat_path_or_hash_stays_but_is_ineligible(self):
        reviews = self.complete_reviews()
        first_path = reviews[0]["extracted_fields"]["photo_path"]
        reviews[1]["extracted_fields"]["photo_path"] = first_path
        twin = self.make_photo("twin-of-review-1.jpg", b"photo-1")
        reviews[2]["extracted_fields"]["photo_path"] = str(twin)
        records = builder.build_teaching_records(reviews, set())
        self.assertTrue(records[0]["reader_example_eligible"])
        self.assertFalse(records[1]["reader_example_eligible"])
        self.assertFalse(records[2]["reader_example_eligible"])

    def test_05_builder_rejects_missing_or_duplicate_reviews(self):
        records = self.complete_reviews()
        records.append({
            "source_id": "rules", "id": "spine-rules",
            "extracted_fields": {"record_type": "approved_teaching_rules", "rules": ["one"]},
        })
        self.assertEqual(len(builder.build_teaching_records(records, set())), 40)
        with self.assertRaises(ValueError):
            builder.build_teaching_records(records[:-2], set())
        changed = self.complete_reviews()
        changed[-1]["source_id"] = "photo-01"
        with self.assertRaises(ValueError):
            builder.build_teaching_records(changed, set())

    def test_06_review_paths_and_hashes_cannot_enter_test(self):
        self.make_photo("review-a.jpg", b"different")
        note = {"source_id": "n1", "path": "review-a.jpg", "tags": ["sedum"]}
        with self.assertRaises(engine.RunLimitError):
            engine.select_unseen_notes([note], self.root, self.teaching, set(), 10, 7)

    def test_07_target_never_teaches_itself_with_resolved_path(self):
        target = {"job_ref": "1000-26", "source_path": str(self.root / "nested" / ".." / "review-a.jpg"), "source_sha256": "other"}
        examples = engine.select_approved_examples(target, self.teaching, self.root)
        self.assertFalse(any(row["source_path"] == "review-a.jpg" for row in examples))

    def test_08_examples_are_same_job_only_and_no_fallback(self):
        examples = engine.select_approved_examples({"job_ref": "1000-26", "source_path": "x.jpg", "source_sha256": "x"}, self.teaching, self.root)
        self.assertTrue(examples)
        self.assertTrue(all(row["job_ref"] == "1000-26" for row in examples))
        self.assertEqual(engine.select_approved_examples({"job_ref": "none", "source_path": "x.jpg", "source_sha256": "x"}, self.teaching, self.root), [])

    def test_09_folder_ignores_non_photo_files(self):
        self.make_photo("one.jpg")
        self.make_photo("words.txt")
        self.make_photo("sidecar.json")
        self.make_photo("clip.mov")
        self.assertEqual([path.name for path in engine.photo_files_in_folder(self.root)], ["one.jpg"])

    def test_10_folder_refuses_eleven_before_labelling(self):
        for number in range(11):
            self.make_photo(f"{number:02}.jpg", str(number).encode())
        with patch.object(engine, "label_photo") as label:
            with self.assertRaises(engine.RunLimitError):
                engine.run_folder(self.root, self.root / "runs", set(), [], labeler=label)
        label.assert_not_called()

    def test_11_folder_labels_ten_in_path_order(self):
        for number in range(10):
            self.make_photo(f"{9-number:02}.jpg", str(number).encode())
        called = []
        def fake_label(path, *_args, **_kwargs):
            called.append(Path(path).name)
            return ["maintenance visit"]
        run = engine.run_folder(self.root, self.root / "runs", set(), [], labeler=fake_label)
        self.assertEqual(called, sorted(called))
        self.assertEqual(len(json.loads((run / "heldout_results.json").read_text())["results"]), 10)

    def test_12_case_ids_are_stable_across_order(self):
        notes = [
            {"source_id": "same", "path": "same.jpg", "tags": [], "note": "one"},
            {"source_id": "same", "path": "same.jpg", "tags": [], "note": "two"},
            {"source_id": "same", "path": "same.jpg", "tags": [], "note": "one"},
        ]
        first = [row["case_id"] for row in engine.build_case_rows(notes, self.root)]
        second = [row["case_id"] for row in engine.build_case_rows(list(reversed(notes)), self.root)]
        self.assertEqual(first, second)
        self.assertTrue(any(case.endswith("-02") for case in first))

    def test_13_run_binding_blocks_another_judge_or_sheet(self):
        run = self.root / "run-a"
        run.mkdir()
        (run / "manifest.json").write_text(json.dumps({"run_id": "run-a"}))
        (run / "heldout_results.json").write_text(json.dumps({"run_id": "run-a", "results": []}))
        (run / "note_judge.json").write_text(json.dumps({"run_id": "run-b", "judged": []}))
        with self.assertRaises(ValueError):
            judge.load_run(run)
        with self.assertRaises(ValueError):
            sheet.load_run_data(run)

    def test_14_small_run_writes_ten_bound_cases_and_manifest(self):
        base = self.root / "base"
        grind = base / "grind"
        grind.mkdir(parents=True)
        teaching_path = grind / "fewshot_approved_teaching_20260801.json"
        teaching_path.write_text(json.dumps(builder.build_teaching_records(self.complete_reviews(), set())))
        excluded_path = grind / "excluded_moves_20260728.jsonl"
        excluded_path.write_text("")
        notes = []
        for number in range(10):
            path = base / f"photo-{number}.jpg"
            path.write_bytes(str(number).encode())
            notes.append({"source_id": f"note-{number}", "path": path.name, "tags": ["sedum"], "note": "sedum", "job": "1000-26"})
        notes_path = base / "knowledge_notes.jsonl"
        notes_path.write_text("\n".join(json.dumps(row) for row in notes) + "\n")
        ledger_path = base / "photo_ledger_merged.jsonl"
        ledger_path.write_text("")
        run = engine.run_test_small(base, teaching_path, excluded_path, notes_path, ledger_path, labeler=lambda *_args: ["pregrown sedum"])
        manifest = json.loads((run / "manifest.json").read_text())
        results = json.loads((run / "heldout_results.json").read_text())
        baseline = json.loads((run / "baseline_keyword.json").read_text())
        self.assertEqual(len(results["results"]), 10)
        self.assertEqual(manifest["seed"], engine.FIXED_TEST_SEED)
        self.assertEqual(manifest["requested_count"], 10)
        self.assertEqual(results["run_id"], run.name)
        self.assertEqual(baseline["run_id"], run.name)
        self.assertIn("withheld", manifest)

    def test_15_builder_reads_the_real_approved_spine_shape(self):
        reviews = self.complete_reviews()
        records = builder.build_teaching_records(reviews, set())
        self.assertEqual(len(records), 40)
        for review, record in zip(reviews, records):
            photo = Path(review["extracted_fields"]["photo_path"])
            self.assertEqual(record["source_path"], str(photo))
            self.assertEqual(record["source_sha256"], engine.sha256_of(photo))
            self.assertEqual(record["approved_summary"], review["extracted_fields"]["approved_summary"])

    def test_16_builder_refuses_a_source_photo_it_cannot_hash(self):
        reviews = self.complete_reviews()
        reviews[7]["extracted_fields"]["photo_path"] = str(self.root / "gone.jpg")
        with self.assertRaises(ValueError):
            builder.build_teaching_records(reviews, set())

    def test_17_reviewed_photo_is_withheld_when_teaching_holds_an_absolute_path(self):
        photo = self.make_photo("seen-before.jpg", b"already reviewed")
        teaching = [{
            "teaching_id": "lee-review-20260801:photo-01", "job_ref": "1000-26",
            "source_path": str(photo), "source_sha256": "not-the-real-hash",
            "approved_summary": "roof edge", "reader_example_eligible": True,
        }]
        note = {"source_id": "n1", "path": photo.name, "tags": ["sedum"]}
        with self.assertRaises(engine.RunLimitError):
            engine.select_unseen_notes([note], self.root, teaching, set(), 1, 7)

    # --- The ID ladder lanes. Rail: ~/.claude/skills/green-roof-image-plane/SKILL.md ---

    def ladder_sources(self, register_rows=(), points_rows=(), located=None):
        """Build the three recorded sources in their real shape."""
        return {
            "register": {row["path"]: row for row in register_rows},
            "points": {row["path"]: (row["lat"], row["lon"]) for row in points_rows},
            "located_jobs": located or {},
        }

    def unknown_target(self, name="mystery.jpg", sha="mystery-sha"):
        """A picture whose job field says the word unknown."""
        photo = self.make_photo(name, name.encode())
        return {"job_ref": "unknown", "source_path": str(photo),
                "absolute_path": str(photo), "source_sha256": sha}, str(photo)

    def teaching_for(self, job="1000-26"):
        return [{
            "teaching_id": "lee-review-20260801:photo-01", "job_ref": job,
            "source_path": "review-a.jpg", "source_sha256": "ra",
            "approved_summary": "roof edge", "reader_example_eligible": True,
        }]

    def test_19_unknown_job_still_reads_and_two_lanes_give_it_an_example(self):
        target, path = self.unknown_target()
        sources = self.ladder_sources(
            register_rows=[{"path": path, "job_ref": "1000-26", "method": "album", "confidence": "high"}],
            points_rows=[{"path": path, "lat": 51.5, "lon": -0.1}],
            located={"1000-26": {"lat": 51.5, "lon": -0.1}},
        )
        examples, resolution = engine.resolve_examples(target, self.teaching_for(), self.root, sources)
        self.assertEqual(resolution["job_ref"], "1000-26")
        self.assertEqual(resolution["method"], "lane7_photo_register+lane2_gra_sites")
        self.assertEqual([row["teaching_id"] for row in examples], ["lee-review-20260801:photo-01"])

    def test_20_position_alone_gives_no_example(self):
        target, path = self.unknown_target()
        sources = self.ladder_sources(
            points_rows=[{"path": path, "lat": 51.5, "lon": -0.1}],
            located={"1000-26": {"lat": 51.5, "lon": -0.1}},
        )
        examples, resolution = engine.resolve_examples(target, self.teaching_for(), self.root, sources)
        self.assertEqual(examples, [])
        self.assertIsNone(resolution["job_ref"])
        self.assertIn("One lane is not enough", resolution["reason"])

    def test_21_register_found_by_position_is_the_same_lane_twice(self):
        target, path = self.unknown_target()
        sources = self.ladder_sources(
            register_rows=[{"path": path, "job_ref": "1000-26", "method": "gps_nn", "confidence": "high"}],
            points_rows=[{"path": path, "lat": 51.5, "lon": -0.1}],
            located={"1000-26": {"lat": 51.5, "lon": -0.1}},
        )
        examples, resolution = engine.resolve_examples(target, self.teaching_for(), self.root, sources)
        self.assertEqual(examples, [])
        self.assertIsNone(resolution["job_ref"])
        self.assertIn("position cannot confirm it", resolution["reason"])

    def test_22_lanes_that_disagree_go_to_lee(self):
        target, path = self.unknown_target()
        sources = self.ladder_sources(
            register_rows=[{"path": path, "job_ref": "1858-26", "method": "date_split", "confidence": "high"}],
            points_rows=[{"path": path, "lat": 51.5, "lon": -0.1}],
            located={"1301-21": {"lat": 51.5, "lon": -0.1}},
        )
        examples, resolution = engine.resolve_examples(target, self.teaching_for("1858-26"), self.root, sources)
        self.assertEqual(examples, [])
        self.assertIsNone(resolution["job_ref"])
        self.assertIn("1858-26", resolution["reason"])
        self.assertIn("1301-21", resolution["reason"])
        self.assertIn("goes to Lee", resolution["reason"])

    def test_22a_the_known_mistype_is_one_job_not_two_sites(self):
        """Lee, 1 Aug 2026: "1588 is a known mistype ... just combine them".

        This is the exact case that was carried as ambiguous: the register said
        1858-26, the position said 1588-26, and they stood 18 metres apart. It
        was never two sites. It is one job typed two ways, so the lanes agree.
        """
        target, path = self.unknown_target("mistype.jpg", "sha-mistype")
        sources = self.ladder_sources(
            register_rows=[{"path": path, "job_ref": "1858-26", "method": "date_split", "confidence": "high"}],
            points_rows=[{"path": path, "lat": 51.5, "lon": -0.1}],
            located={"1588-26": {"lat": 51.5, "lon": -0.1}},
        )
        examples, resolution = engine.resolve_examples(target, self.teaching_for("1858-26"), self.root, sources)
        self.assertEqual(resolution["job_ref"], "1858-26")
        self.assertIsNone(resolution["reason"])
        self.assertTrue(examples)

    def test_22b_a_register_row_naming_two_lanes_stands_on_its_own(self):
        """Lee, 1 Aug 2026: "five routes doesnt need extra".

        The row already names five lanes, so the never-one-field law is met
        inside the row. There is no position for this picture at all, and the
        band is not high. Neither test may refuse it.
        """
        target, path = self.unknown_target("five-routes.jpg", "sha-five")
        sources = self.ladder_sources(
            register_rows=[{"path": path, "job_ref": "1858-26", "confidence": "medium",
                            "method": "lane2_gra_sites+lane3_project_folders+lane4_xero"
                                      "+lane5_mail+lane7_photo_register"}],
        )
        examples, resolution = engine.resolve_examples(target, self.teaching_for("1858-26"), self.root, sources)
        self.assertEqual(resolution["job_ref"], "1858-26")
        self.assertIsNone(resolution["reason"])
        self.assertIn("lane2", resolution["method"])
        self.assertIn("lane7", resolution["method"])
        self.assertTrue(examples)

    def test_23_medium_or_low_band_gives_no_example(self):
        for band in ("medium", "low"):
            with self.subTest(band=band):
                target, path = self.unknown_target(f"band-{band}.jpg", f"sha-{band}")
                sources = self.ladder_sources(
                    register_rows=[{"path": path, "job_ref": "1000-26", "method": "album", "confidence": band}],
                    points_rows=[{"path": path, "lat": 51.5, "lon": -0.1}],
                    located={"1000-26": {"lat": 51.5, "lon": -0.1}},
                )
                examples, resolution = engine.resolve_examples(target, self.teaching_for(), self.root, sources)
                self.assertEqual(examples, [])
                self.assertIsNone(resolution["job_ref"])
                self.assertIn(band, resolution["reason"])

    def test_24_lee_answer_in_the_register_stands_on_its_own(self):
        target, path = self.unknown_target()
        sources = self.ladder_sources(
            register_rows=[{"path": path, "job_ref": "1000-26",
                            "method": "lee_cluster_answer", "confidence": "lee_confirmed"}],
        )
        examples, resolution = engine.resolve_examples(target, self.teaching_for(), self.root, sources)
        self.assertEqual(resolution["job_ref"], "1000-26")
        self.assertEqual(resolution["method"], "lee_answer")
        self.assertEqual([row["teaching_id"] for row in examples], ["lee-review-20260801:photo-01"])

    def test_24a_lee_answer_by_the_method_alone_stands(self):
        """The row says Lee answered it, but the band is only medium.

        Split out on 5 Aug 2026. The mutation harness proved test_24 did not
        bite: it set the method AND the band, so either one alone satisfied it
        and neither was guarded.
        """
        target, path = self.unknown_target("lee-method.jpg", "sha-lee-method")
        sources = self.ladder_sources(
            register_rows=[{"path": path, "job_ref": "1000-26",
                            "method": "lee_cluster_answer", "confidence": "medium"}],
        )
        examples, resolution = engine.resolve_examples(target, self.teaching_for(), self.root, sources)
        self.assertEqual(resolution["job_ref"], "1000-26")
        self.assertEqual(resolution["method"], "lee_answer")
        self.assertTrue(examples)

    def test_24b_lee_answer_by_the_band_alone_stands(self):
        """The band says Lee confirmed it, but the method is an ordinary one."""
        target, path = self.unknown_target("lee-band.jpg", "sha-lee-band")
        sources = self.ladder_sources(
            register_rows=[{"path": path, "job_ref": "1000-26",
                            "method": "album", "confidence": "lee_confirmed"}],
        )
        examples, resolution = engine.resolve_examples(target, self.teaching_for(), self.root, sources)
        self.assertEqual(resolution["job_ref"], "1000-26")
        self.assertEqual(resolution["method"], "lee_answer")
        self.assertTrue(examples)

    def test_25_no_picture_can_teach_itself_by_path_or_by_hash(self):
        photo = self.make_photo("self.jpg", b"self")
        teaching = [
            {"teaching_id": "same-path", "job_ref": None, "source_path": str(photo),
             "source_sha256": "different-hash", "approved_summary": "x", "reader_example_eligible": True},
            {"teaching_id": "same-hash", "job_ref": None, "source_path": str(self.root / "twin.jpg"),
             "source_sha256": "shared-hash", "approved_summary": "x", "reader_example_eligible": True},
        ]
        register = {
            str(photo): {"path": str(photo), "job_ref": "1000-26", "method": "album", "confidence": "high"},
            str(self.root / "twin.jpg"): {"path": str(self.root / "twin.jpg"), "job_ref": "1000-26",
                                          "method": "album", "confidence": "high"},
        }
        points = {str(photo): (51.5, -0.1), str(self.root / "twin.jpg"): (51.5, -0.1)}
        sources = {"register": register, "points": points, "located_jobs": {"1000-26": {"lat": 51.5, "lon": -0.1}}}
        target = {"job_ref": "unknown", "source_path": str(photo), "absolute_path": str(photo),
                  "source_sha256": "shared-hash"}
        examples, resolution = engine.resolve_examples(target, teaching, self.root, sources)
        self.assertEqual(resolution["job_ref"], "1000-26")
        self.assertEqual(examples, [])
        self.assertIn("no approved example belongs to it", resolution["reason"])

    def test_26_every_result_row_carries_the_lane_and_a_reason(self):
        base = self.root / "laned"
        grind = base / "grind"
        grind.mkdir(parents=True)
        teaching_path = grind / "fewshot_approved_teaching_20260801.json"
        teaching_path.write_text(json.dumps(builder.build_teaching_records(self.complete_reviews(), set())))
        excluded_path = grind / "excluded_moves_20260728.jsonl"
        excluded_path.write_text("")
        notes = []
        for number in range(10):
            path = base / f"photo-{number}.jpg"
            path.write_bytes(f"laned-{number}".encode())
            notes.append({"source_id": f"note-{number}", "path": path.name, "tags": ["sedum"],
                          "note": "sedum", "job": "unknown"})
        notes_path = base / "knowledge_notes.jsonl"
        notes_path.write_text("\n".join(json.dumps(row) for row in notes) + "\n")
        ledger_path = base / "photo_ledger_merged.jsonl"
        ledger_path.write_text("")
        register = {str(base / "photo-0.jpg"): {"path": str(base / "photo-0.jpg"), "job_ref": "1000-26",
                                                "method": "album", "confidence": "high"}}
        sources = {"register": register, "points": {str(base / "photo-0.jpg"): (51.5, -0.1)},
                   "located_jobs": {"1000-26": {"lat": 51.5, "lon": -0.1}},
                   "source_counts": {"register": 1, "points": 1, "located_jobs": 1}, "absent_sources": []}
        run = engine.run_test_small(base, teaching_path, excluded_path, notes_path, ledger_path,
                                    labeler=lambda *_args: ["pregrown sedum"], sources=sources)
        rows = json.loads((run / "heldout_results.json").read_text())["results"]
        self.assertEqual(len(rows), 10)
        for row in rows:
            self.assertIn("job_method", row)
            if not row["example_ids"]:
                self.assertTrue(row["no_example_reason"], row)
        taught = [row for row in rows if row["example_ids"]]
        self.assertEqual([row["job_method"] for row in taught], ["lane7_photo_register+lane2_gra_sites"])
        manifest = json.loads((run / "manifest.json").read_text())
        self.assertEqual(manifest["ladder_sources"], {"register": 1, "points": 1, "located_jobs": 1})

    def test_18_note_with_no_picture_location_is_skipped_not_fatal(self):
        good = self.make_photo("kept.jpg", b"kept")
        notes = [
            {"source_id": "empty", "path": None, "tags": ["sedum"]},
            {"source_id": "kept", "path": good.name, "tags": ["sedum"]},
        ]
        rows = engine.build_case_rows(notes, self.root)
        self.assertEqual(len(rows), 2)
        selected = engine.select_unseen_notes(notes, self.root, [], set(), 1, 7)
        self.assertEqual([row["source_path"] for row in selected], [good.name])


if __name__ == "__main__":
    unittest.main(verbosity=2)
