"""Core logic for the Unsiloed AI internal-ops MCP server (all MOCK data).

Kept free of any MCP import so every tool can be tested with plain Python.
server.py is a thin wrapper that exposes these functions over MCP.
Every function returns a short, plain-text string: cheap on tokens and easy
for smaller models to read.
"""
import difflib
import json
import os

from rag import PlaybookIndex, estimate_tokens

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
MAX_DIFFS_SHOWN = 10
_cache = {}


def _load(name):
    if name not in _cache:
        with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
            _cache[name] = json.load(f)
    return _cache[name]


def _index():
    if "index" not in _cache:
        _cache["index"] = PlaybookIndex(os.path.join(DATA_DIR, "playbook"))
    return _cache["index"]


def _norm(s):
    return str(s).strip().upper()


# ---------------------------------------------------------------------------
# Tool 1: get_parse_job
# ---------------------------------------------------------------------------
def get_parse_job(job_id: str) -> str:
    job_id = _norm(job_id)
    job = next((j for j in _load("jobs.json") if j["job_id"] == job_id), None)
    if job is None:
        return (f"Job '{job_id}' not found. Job IDs look like JOB-1001 to JOB-1030 "
                f"(for example JOB-1004).")
    types = _load("document_types.json")
    expected = types[job["doc_type"]]["expected_sec_per_page"] * job["pages"]
    lines = [f"{job['job_id']}: {job['status']}",
             f"Customer: {job['customer']} | batch {job['batch_id']} | parser {job['parser_version']}",
             f"Document: {job['doc_type']}, {job['pages']} pages | submitted {job['submitted_at']}"]
    if job["status"] == "completed":
        lines.append(f"Took {job['duration_sec']}s (expected about {expected}s).")
    elif job["status"] == "processing":
        el = job["elapsed_sec"]
        if el > 3 * expected:
            lines.append(f"WARNING: running for {el}s but expected about {expected}s. "
                         f"Possibly stuck. See search_failure_playbook('stuck job timeout').")
        else:
            lines.append(f"Running for {el}s (expected about {expected}s). Looks healthy.")
    elif job["status"] == "queued":
        lines.append("Waiting in the queue. Not started yet.")
    for err in job["errors"]:
        lines.append(f"Error: {err}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 2: check_batch_quality  (proactive: flags problems before delivery)
# ---------------------------------------------------------------------------
def check_batch_quality(batch_id: str, threshold: float = 0.80) -> str:
    batch_id = _norm(batch_id)
    batch = next((b for b in _load("batches.json") if b["batch_id"] == batch_id), None)
    if batch is None:
        return f"Batch '{batch_id}' not found. Batch IDs look like BATCH-01 to BATCH-05."
    try:
        threshold = float(threshold)
    except (TypeError, ValueError):
        return "threshold must be a number between 0 and 1, for example 0.80."
    if not 0 < threshold <= 1:
        return "threshold must be a number between 0 and 1, for example 0.80."
    flagged = [p for p in batch["pages"]
               if p["confidence"] < threshold or p["issue_type"] or p["missing_fields"]]
    lines = [f"{batch_id} ({batch['customer']}, parser {batch['parser_version']}, "
             f"status {batch['status']}): {len(batch['pages'])} pages checked, "
             f"{len(flagged)} flagged (confidence threshold {threshold:.2f})."]
    for p in flagged[:25]:
        why = []
        if p["confidence"] < threshold:
            why.append(f"confidence {p['confidence']:.2f}")
        if p["issue_type"]:
            why.append(f"issue {p['issue_type']}")
        if p["missing_fields"]:
            why.append("missing fields " + ",".join(p["missing_fields"]))
        lines.append(f"- {p['job_id']} page {p['page']}: " + "; ".join(why))
    if len(flagged) > 25:
        lines.append(f"... and {len(flagged) - 25} more.")
    if flagged:
        lines.append("Next: run compare_source_vs_parsed(job_id, page) on flagged pages to see "
                     "exactly what is wrong.")
    lines.append("Note: high confidence does not guarantee correct output. Confident errors "
                 "(dropped digits, lost footnotes, wrong reading order) are only found by "
                 "compare_source_vs_parsed.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 3: compare_source_vs_parsed  (customer original vs what we produced)
# ---------------------------------------------------------------------------
def _compare_blocks(sb, pb, diffs):
    total, matched = len(sb), 0
    if sorted(sb) == sorted(pb) and sb != pb:
        pos = [i + 1 for i, (a, b) in enumerate(zip(sb, pb)) if a != b]
        diffs.append({"type": "reading_order_changed", "where": "Text",
                      "detail": f"all text present, but blocks at positions {pos} are in a different order"})
        return total, sum(a == b for a, b in zip(sb, pb))
    rest = list(pb)
    for b in sb:
        if b in rest:
            rest.remove(b)
            matched += 1
            continue
        close = difflib.get_close_matches(b, rest, n=1, cutoff=0.6)
        if close:
            rest.remove(close[0])
            diffs.append({"type": "text_changed", "where": "Text",
                          "detail": f"source '{b}' -> parsed '{close[0]}'"})
        else:
            diffs.append({"type": "text_missing", "where": "Text",
                          "detail": f"'{b}' is in the source but not in the parsed output"})
    for b in rest:
        diffs.append({"type": "text_extra", "where": "Text",
                      "detail": f"'{b}' is in the parsed output but not in the source"})
    return total, matched


def _compare_tables(st_list, pt_list, diffs):
    total = matched = 0
    for ti, st in enumerate(st_list):
        total += sum(len(r) for r in st)
        if ti >= len(pt_list):
            diffs.append({"type": "table_missing", "where": f"Table {ti + 1}",
                          "detail": "present in the source, missing in the parsed output"})
            continue
        pt, header = pt_list[ti], st[0]
        unused = list(range(len(pt)))
        unmatched = []
        # 1) exact row matches
        for ri, srow in enumerate(st):
            hit = next((j for j in unused if pt[j] == srow), None)
            if hit is None:
                unmatched.append(ri)
            else:
                unused.remove(hit)
                matched += len(srow)
        # 2) same text but different cell count -> merged or split cells
        remaining = []
        for ri in unmatched:
            srow = st[ri]
            toks = " ".join(srow).split()
            hit = next((j for j in unused if len(pt[j]) != len(srow)
                        and " ".join(pt[j]).split() == toks), None)
            if hit is None:
                remaining.append(ri)
                continue
            unused.remove(hit)
            matched += max(len(srow) - 2, 0)
            diffs.append({"type": "cell_structure_changed", "where": f"Table {ti + 1}, row {ri + 1}",
                          "detail": f"expected {len(srow)} cells, got {len(pt[hit])} (cells merged or split): "
                                    f"source {srow} -> parsed {pt[hit]}"})
        # 3) similar row with some cells changed -> value changes
        for ri in remaining:
            srow = st[ri]
            best, best_eq = None, -1
            for j in unused:
                if len(pt[j]) == len(srow):
                    eq = sum(a == b for a, b in zip(srow, pt[j]))
                    if eq > best_eq:
                        best, best_eq = j, eq
            if best is not None and best_eq * 2 >= len(srow):
                unused.remove(best)
                matched += best_eq
                for ci, (a, b) in enumerate(zip(srow, pt[best])):
                    if a != b:
                        col = header[ci] if ci < len(header) else str(ci + 1)
                        diffs.append({"type": "value_changed",
                                      "where": f"Table {ti + 1}, row {ri + 1}, col '{col}'",
                                      "detail": f"source '{a}' -> parsed '{b}'"})
            else:
                diffs.append({"type": "row_missing", "where": f"Table {ti + 1}, row {ri + 1}",
                              "detail": f"source row {srow} not found in the parsed output"})
        for j in unused:
            diffs.append({"type": "extra_row", "where": f"Table {ti + 1}",
                          "detail": f"parsed row {pt[j]} does not exist in the source"})
    return total, matched


def _compare_list(src, par, kind, label, diffs):
    matched = 0
    for item in src:
        if item in par:
            matched += 1
        else:
            diffs.append({"type": f"{kind}_missing", "where": label,
                          "detail": f"'{item}' is in the source but missing in the parsed output"})
    return len(src), matched


def compare_pages(source: dict, parsed: dict) -> dict:
    """Compare one source page with its parsed version. Returns score + differences."""
    diffs = []
    t1, m1 = _compare_blocks(source["blocks"], parsed["blocks"], diffs)
    t2, m2 = _compare_tables(source["tables"], parsed["tables"], diffs)
    t3, m3 = _compare_list(source["charts"], parsed["charts"], "chart", "Chart", diffs)
    t4, m4 = _compare_list(source["footnotes"], parsed["footnotes"], "footnote", "Footnote", diffs)
    total, matched = t1 + t2 + t3 + t4, m1 + m2 + m3 + m4
    return {"match_pct": round(100 * matched / total, 1) if total else 100.0,
            "differences": diffs}


def compare_source_vs_parsed(job_id: str, page: int) -> str:
    job_id = _norm(job_id)
    try:
        page = int(page)
    except (TypeError, ValueError):
        return "page must be a whole number, for example 1."
    pairs = _load("pages.json")
    key = f"{job_id}:{page}"
    if key not in pairs:
        avail = ", ".join(f"{k.split(':')[0]} p{k.split(':')[1]}" for k in pairs)
        return (f"No source/parsed pair stored for {job_id} page {page}. "
                f"Pairs available in this demo: {avail}.")
    res = compare_pages(pairs[key]["source"], pairs[key]["parsed"])
    diffs = res["differences"]
    head = (f"{job_id}, page {page}: "
            + ("no differences found" if not diffs else f"{len(diffs)} difference(s)")
            + f" (match {res['match_pct']}%)")
    lines = [head]
    for d in diffs[:MAX_DIFFS_SHOWN]:
        lines.append(f"- [{d['type']}] {d['where']}: {d['detail']}")
    if len(diffs) > MAX_DIFFS_SHOWN:
        lines.append(f"... and {len(diffs) - MAX_DIFFS_SHOWN} more.")
    if diffs:
        lines.append("Next: search_failure_playbook with the difference type for the known cause and fix.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 4: run_regression_check  (does a parser update make old documents worse?)
# ---------------------------------------------------------------------------
def run_regression_check(old_version: str = "v1.4", new_version: str = "v2.0") -> str:
    samples = _load("regression_samples.json")
    versions = sorted({v for s in samples.values() for v in s["outputs"]})
    for v in (old_version, new_version):
        if v not in versions:
            return f"Unknown parser version '{v}'. Available versions: {', '.join(versions)}."
    if old_version == new_version:
        return "old_version and new_version are the same. Pick two different versions."
    regressed, improved, same = [], [], 0
    for sid, s in samples.items():
        old = compare_pages(s["source"], s["outputs"][old_version])
        new = compare_pages(s["source"], s["outputs"][new_version])
        old_types = {d["type"] for d in old["differences"]}
        new_types = sorted({d["type"] for d in new["differences"]} - old_types)
        row = (sid, s["doc_type"], old["match_pct"], new["match_pct"], new_types)
        if new["match_pct"] < old["match_pct"]:
            regressed.append(row)
        elif new["match_pct"] > old["match_pct"]:
            improved.append(row)
        else:
            same += 1
    lines = [f"Regression check {old_version} -> {new_version} on {len(samples)} saved sample documents:",
             f"Regressed (worse in {new_version}): {len(regressed)}"]
    for sid, dt, o, n, types in regressed:
        lines.append(f"- {sid} ({dt}): {o}% -> {n}%; new problems: {', '.join(types) or 'none'}")
    lines.append(f"Improved: {len(improved)}")
    for sid, dt, o, n, _ in improved:
        lines.append(f"- {sid} ({dt}): {o}% -> {n}%")
    lines.append(f"Unchanged: {same}")
    if regressed:
        lines.append("Next: hold the rollout for these document types and check search_failure_playbook "
                     "for each new problem type.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 5: search_failure_playbook  (RAG: returns only the relevant chunks)
# ---------------------------------------------------------------------------
def search_failure_playbook(question: str) -> str:
    idx = _index()
    hits = idx.search(question)
    if not hits:
        return ("No matching failure reports found. Try other keywords, for example: "
                "table, merged cells, scan, rotated, chart, footnote, digit, decimal, "
                "reading order, timeout, stuck.")
    parts = [f"[{h['source']}, part {h['part']}]\n{h['text']}" for h in hits]
    returned = sum(h["tokens"] for h in hits)
    parts.append(f"(Returned {len(hits)} chunks, about {returned} tokens. "
                 f"The whole playbook is about {idx.full_tokens} tokens.)")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Resource and prompt text
# ---------------------------------------------------------------------------
def document_types() -> str:
    return json.dumps(_load("document_types.json"), indent=2)


def triage_prompt(batch_id: str) -> str:
    return (f"You are helping the Unsiloed AI support team triage batch {batch_id} before it is "
            f"delivered to the customer. Follow these steps:\n"
            f"1. Call check_batch_quality for {batch_id}.\n"
            f"2. For each flagged page, call compare_source_vs_parsed to find the exact errors. "
            f"Also spot check one unflagged page per job, because confident errors are not flagged.\n"
            f"3. For each type of error found, call search_failure_playbook to find the known "
            f"cause and fix.\n"
            f"4. Write a short summary for a HUMAN reviewer: what is wrong, which pages, the "
            f"suggested fix, and whether the batch is safe to deliver. Do not send anything to the "
            f"customer yourself.")
