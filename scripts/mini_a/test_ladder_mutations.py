#!/usr/bin/env python3
"""THE MUTATION HARNESS — it proves the ladder checks actually bite.

A test suite that passes proves nothing on its own. It might pass because the
rule holds, or it might pass because the test never looks. The only way to tell
is to BREAK each rule on purpose and watch the matching test go red.

Board ref 300 and the photo lane. Lee's standing law: a fix must make the broken
rule impossible to break again. A check that does not bite is not a guard.

HOW IT WORKS. For each rule below, this program:
  1. copies fewshot_engine.py and test_fewshot_pipeline.py into a scratch folder,
  2. breaks ONE rule in the copy, by a plain text replacement,
  3. runs the pipeline suite in that folder,
  4. and requires the named test to FAIL.

Nothing is written outside the scratch folder. The real files are never touched.
It also runs the clean copy first and requires every test to pass, so a broken
harness cannot be mistaken for a biting one.

Run: python3 test_ladder_mutations.py
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = HERE / "fewshot_engine.py"
SUITE = HERE / "test_fewshot_pipeline.py"
# The suite imports these too, so the scratch folder needs all of them.
COMPANIONS = [
    HERE / "build_fewshot_teaching.py",
    HERE / "fewshot_contact_sheet.py",
    HERE / "fewshot_note_judge.py",
]

# Each row: the rule in plain words, the test that guards it, and the break.
# The break is (find, replace) against the engine source. Both must be exact.
MUTATIONS = [
    (
        "Two lanes that agree give the picture an example",
        "test_19_unknown_job_still_reads_and_two_lanes_give_it_an_example",
        ('return {"job_ref": registered, "method": "lane7_photo_register+lane2_gra_sites", "reason": None}',
         'return {"job_ref": None, "method": None, "reason": "broken on purpose"}'),
    ),
    (
        "The position lane alone is not enough",
        "test_20_position_alone_gives_no_example",
        ('return {"job_ref": None, "method": None,\n                    "reason": "Only the position lane found a job. One lane is not enough."}',
         'return {"job_ref": by_location, "method": "lane2_gra_sites", "reason": None}'),
    ),
    (
        "A register row found by position cannot be confirmed by position",
        "test_21_register_found_by_position_is_the_same_lane_twice",
        ('return str(method or "").lower().startswith("gps")',
         'return False'),
    ),
    (
        "Two lanes that disagree go to Lee and are never picked automatically",
        "test_22_lanes_that_disagree_go_to_lee",
        ("if by_location and by_location != registered:",
         "if False and by_location != registered:"),
    ),
    (
        "1588-26 is a known mistype of 1858-26 and they are one job",
        "test_22a_the_known_mistype_is_one_job_not_two_sites",
        ('JOB_REF_ALIASES = {\n    "1588-26": "1858-26",\n}',
         "JOB_REF_ALIASES = {}"),
    ),
    (
        "A register row that already names two lanes stands on its own",
        "test_22b_a_register_row_naming_two_lanes_stands_on_its_own",
        ("if len(routes) >= 2:",
         "if len(routes) >= 99:"),
    ),
    (
        "A medium or low band is not good enough",
        "test_23_medium_or_low_band_gives_no_example",
        ('if band != "high":',
         'if band != "this band never occurs":'),
    ),
    (
        "Lee's own answer stands on its own, said by the method",
        "test_24a_lee_answer_by_the_method_alone_stands",
        ('LEE_ANSWER_METHODS = {"lee_cluster_answer", "lee_verdict", "lee_answer"}',
         "LEE_ANSWER_METHODS = set()"),
    ),
    (
        "Lee's own answer stands on its own, said by the band",
        "test_24b_lee_answer_by_the_band_alone_stands",
        ('LEE_ANSWER_BANDS = {"lee_confirmed", "lee"}',
         "LEE_ANSWER_BANDS = set()"),
    ),
    (
        "No picture may teach itself, by path or by hash",
        "test_25_no_picture_can_teach_itself_by_path_or_by_hash",
        ("if review_path == target_path or review_sha == target_sha:",
         "if False:"),
    ),
    (
        "A job named 'unknown' is not a job",
        "test_19_unknown_job_still_reads_and_two_lanes_give_it_an_example",
        ('NO_JOB_WORDS = {"", "unknown", "none", "n/a", "-"}',
         'NO_JOB_WORDS = {""}'),
    ),
]


def run_suite(folder: Path) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, "test_fewshot_pipeline.py"],
        cwd=folder, capture_output=True, text=True, timeout=300,
    )
    return result.returncode, result.stdout + result.stderr


def stage(folder: Path) -> None:
    for path in [ENGINE, SUITE, *COMPANIONS]:
        shutil.copy2(path, folder / path.name)


def main() -> int:
    missing = [p for p in [ENGINE, SUITE, *COMPANIONS] if not p.exists()]
    if missing:
        for path in missing:
            print(f"FAIL  cannot find {path}")
        return 2

    passed = 0
    failed = 0

    # The clean run first. A harness that cannot go green proves nothing.
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        stage(folder)
        code, output = run_suite(folder)
        if code == 0:
            print("PASS  the untouched code passes every check")
            passed += 1
        else:
            print("FAIL  the untouched code does not pass. Fix that before reading anything below.")
            print(output[-1500:])
            return 1

    for rule, guard, (find, replace) in MUTATIONS:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            stage(folder)
            engine = folder / ENGINE.name
            source = engine.read_text()

            if find not in source:
                print(f"FAIL  {rule}\n      the break no longer matches the code, so this rule is UNPROVEN")
                failed += 1
                continue
            engine.write_text(source.replace(find, replace, 1))

            code, output = run_suite(folder)
            if code == 0:
                print(f"FAIL  {rule}\n      the rule was broken and every test still passed. "
                      f"{guard} does not bite.")
                failed += 1
            elif guard in output:
                print(f"PASS  {rule}\n      broke it, and {guard} went red")
                passed += 1
            else:
                print(f"FAIL  {rule}\n      breaking it turned the suite red, but not {guard}. "
                      f"Something else caught it, so this rule is not guarded by its own check.")
                failed += 1

    print(f"\n{passed} PASS  {failed} FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
