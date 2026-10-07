"""Plain-Python tests for the tool logic. Run:  python tests/test_tools.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402


def test_job_found():
    assert "JOB-1004: completed" in core.get_parse_job("job-1004")


def test_job_not_found_is_helpful():
    out = core.get_parse_job("JOB-9999")
    assert "not found" in out and "JOB-1001" in out


def test_failed_job_shows_error():
    assert "TIMEOUT_OCR" in core.get_parse_job("JOB-1009")


def test_stuck_job_is_warned():
    assert "Possibly stuck" in core.get_parse_job("JOB-1017")


def test_healthy_processing_job_not_warned():
    out = core.get_parse_job("JOB-1028")
    assert "Looks healthy" in out and "stuck" not in out.lower()


def test_quality_flags_bad_batch():
    out = core.check_batch_quality("BATCH-03")
    assert "JOB-1013 page 1" in out and "JOB-1015 page 1" in out


def test_quality_clean_batch_has_no_flags():
    assert " 0 flagged" in core.check_batch_quality("BATCH-01")


def test_quality_misses_confident_errors():
    # JOB-1004 p1 has a dropped digit but 0.97 confidence: quality check can't see it ...
    assert "JOB-1004" not in core.check_batch_quality("BATCH-01")
    # ... but the compare tool does.
    assert "value_changed" in core.compare_source_vs_parsed("JOB-1004", 1)


def test_quality_rejects_bad_threshold():
    assert "between 0 and 1" in core.check_batch_quality("BATCH-01", 5)


EXPECTED = {("JOB-1004", 1): "value_changed", ("JOB-1011", 2): "row_missing",
            ("JOB-1013", 1): "cell_structure_changed", ("JOB-1013", 2): "chart_missing",
            ("JOB-1016", 1): "footnote_missing", ("JOB-1016", 2): "reading_order_changed"}


def test_each_planted_error_is_found():
    for (job, page), kind in EXPECTED.items():
        out = core.compare_source_vs_parsed(job, page)
        assert kind in out, f"{job} p{page}: expected {kind}\n{out}"


def test_clean_pages_have_no_differences():
    for job, page in [("JOB-1004", 2), ("JOB-1011", 3)]:
        out = core.compare_source_vs_parsed(job, page)
        assert "no differences found" in out and "match 100.0%" in out


def test_compare_unknown_page_is_helpful():
    assert "Pairs available" in core.compare_source_vs_parsed("JOB-1004", 9)


def test_regression_counts():
    out = core.run_regression_check("v1.4", "v2.0")
    assert "Regressed (worse in v2.0): 3" in out and "Improved: 2" in out
    assert "Unchanged: 5" in out


def test_regression_bad_version():
    assert "Unknown parser version" in core.run_regression_check("v9", "v2.0")


def test_rag_finds_right_report():
    cases = {"two columns merged into one cell": "table_merged_cells",
             "scan is rotated sideways": "rotated_scans",
             "digit dropped from total": "number_format_errors",
             "job stuck timeout": "stuck_jobs_timeouts",
             "text in wrong order two column": "reading_order_errors",
             "footnote missing": "dropped_charts_footnotes"}
    for question, source in cases.items():
        assert source in core.search_failure_playbook(question), question


def test_rag_returns_at_most_3_chunks():
    assert core.search_failure_playbook("table").count("part ") <= 4  # 3 hits + footer wording


def test_rag_no_match_is_helpful():
    assert "No matching failure reports" in core.search_failure_playbook("zzzqqq")


if __name__ == "__main__":
    fns = [f for n, f in sorted(globals().items()) if n.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
