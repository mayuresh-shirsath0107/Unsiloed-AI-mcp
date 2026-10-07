#!/usr/bin/env python3
"""Generate all MOCK data for the Unsiloed AI internal-ops MCP server.

Deterministic (seeded): running it twice gives identical files.
Everything here is invented for the assignment; none of it is real company data.

    python generate_data.py
"""
import copy
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
os.makedirs(DATA, exist_ok=True)
rng = random.Random(7)


def money(x):
    return f"{x:,.2f}"


# --------------------------------------------------------------------------
# Document types (also served as the schema://document-types resource)
# --------------------------------------------------------------------------
DOC_TYPES = {
    "invoice": {
        "description": "Supplier invoices with a line-item table and a total",
        "required_fields": ["invoice_number", "date", "vendor", "line_items", "total"],
        "expected_sec_per_page": 4,
    },
    "bank_statement": {
        "description": "Monthly bank statements with a transaction table",
        "required_fields": ["account_number", "period", "transactions", "closing_balance"],
        "expected_sec_per_page": 5,
    },
    "financial_report": {
        "description": "Quarterly or annual reports with tables, charts and footnotes",
        "required_fields": ["company", "period", "income_statement", "balance_sheet"],
        "expected_sec_per_page": 9,
    },
    "scanned_form": {
        "description": "Scanned application or intake forms (image only)",
        "required_fields": ["form_id", "applicant", "signature_present"],
        "expected_sec_per_page": 7,
    },
    "research_paper": {
        "description": "Two-column research papers with figures and footnotes",
        "required_fields": ["title", "authors", "abstract", "references"],
        "expected_sec_per_page": 6,
    },
}
CUSTOMERS = ["Northwind Capital", "Helix Logistics", "Brightpath Health",
             "Ardent Legal", "Kestrel Insurance"]
VENDORS = ["Orbit Supplies", "Maple Industrial", "Zenith Packaging",
           "Pioneer Tools", "Cedar Office Co"]
ITEMS = ["Widget A", "Widget B", "Bracket Set", "Cable Pack",
         "Safety Gloves", "Label Roll", "Pallet Wrap"]


# --------------------------------------------------------------------------
# Page builders: each returns a "source" page (the mock ground truth)
# A page = {blocks: [text], tables: [[row, ...]], charts: [str], footnotes: [str]}
# --------------------------------------------------------------------------
def invoice_page(r):
    rows, total = [], 0
    for item in r.sample(ITEMS, 4):
        qty = r.randint(2, 20)
        unit = r.choice([45, 80, 120, 300])
        amount = qty * unit
        total += amount
        rows.append([item, str(qty), money(unit), money(amount)])
    table = [["Item", "Qty", "Unit Price", "Amount"]] + rows + [["", "", "Total", money(total)]]
    return {
        "blocks": [f"Invoice INV-{r.randint(1000, 9999)}",
                   f"Vendor: {r.choice(VENDORS)}",
                   f"Date: 2026-09-{r.randint(1, 28):02d}"],
        "tables": [table], "charts": [],
        "footnotes": ["Payment due within 30 days."],
    }


def bank_page(r):
    bal, rows = r.randint(8000, 20000), []
    for d in range(5):
        desc = r.choice(["Payroll", "Rent", "Supplier payment", "Card settlement", "Utility bill"])
        if r.random() < 0.5:
            debit, credit = r.randint(200, 3000), 0
            bal -= debit
        else:
            debit, credit = 0, r.randint(200, 3000)
            bal += credit
        rows.append([f"2026-09-{d * 5 + 1:02d}", desc,
                     money(debit) if debit else "", money(credit) if credit else "", money(bal)])
    table = [["Date", "Description", "Debit", "Credit", "Balance"]] + rows
    return {"blocks": ["Account: ****4821", "Period: Sep 2026"], "tables": [table],
            "charts": [], "footnotes": ["Balances shown in USD."]}


def financial_page(r):
    def q(base):
        return [f"{int(base * f):,}" for f in (1.0, r.uniform(1.03, 1.12), r.uniform(1.12, 1.25))]
    table = [["Metric", "Q1", "Q2", "Q3"],
             ["Revenue"] + q(r.randint(8000, 9000)),
             ["Gross profit"] + q(r.randint(4000, 4500)),
             ["Operating cost"] + q(r.randint(2500, 3000)),
             ["Net income"] + q(r.randint(900, 1400))]
    return {"blocks": ["Quarterly Financial Summary",
                       "Revenue grew steadily across all three quarters."],
            "tables": [table], "charts": ["Revenue by quarter (bar chart)"],
            "footnotes": ["Figures in USD thousands."]}


def research_page(r):
    return {"blocks": ["Abstract: we study how accuracy scales with model size.",
                       f"Our method improves accuracy by {r.randint(3, 9)} percent on average.",
                       "Results are consistent across all five benchmark datasets.",
                       "Section 2 describes the experimental setup in detail."],
            "tables": [], "charts": ["Figure 1: Accuracy vs. model size"],
            "footnotes": ["1. See appendix B for the full dataset description."]}


BUILDERS = {"invoice": invoice_page, "bank_statement": bank_page,
            "financial_report": financial_page, "research_paper": research_page}


# --------------------------------------------------------------------------
# Error injectors: turn a clean "source" page into a faulty "parsed" page
# --------------------------------------------------------------------------
def inj_value(p):       # a digit is dropped: 1,250.00 -> 1,25.00 (last cell of last row)
    t = p["tables"][0]
    v = t[-1][-1]
    i = v.index(".")
    t[-1][-1] = v[:i - 1] + v[i:]


def inj_missing_row(p):  # a whole table row disappears
    del p["tables"][0][3]


def inj_merge(p):        # two neighbouring cells merged into one
    row = p["tables"][0][2]
    row[1:3] = [row[1] + " " + row[2]]


def inj_drop_chart(p):
    p["charts"] = []


def inj_drop_footnote(p):
    p["footnotes"] = []


def inj_swap(p):         # reading order: two text blocks swapped
    b = p["blocks"]
    b[1], b[2] = b[2], b[1]


def faulty(source, *injectors):
    out = copy.deepcopy(source)
    for inj in injectors:
        inj(out)
    return out


# --------------------------------------------------------------------------
# Jobs and batches (30 jobs, 5 batches of 6)
# --------------------------------------------------------------------------
SPEC = {  # job number -> (doc_type, pages) for jobs that matter to the demo
    1004: ("invoice", 2), 1008: ("invoice", 3), 1009: ("scanned_form", 4),
    1011: ("bank_statement", 3), 1013: ("financial_report", 2),
    1015: ("scanned_form", 3), 1016: ("research_paper", 2),
    1017: ("financial_report", 5), 1021: ("financial_report", 3),
    1028: ("invoice", 5),
}
# (job, page) -> (confidence, issue_type, missing_fields)
QUALITY_OVERRIDES = {
    (1004, 1): (0.97, None, []),                      # CONFIDENT BUT WRONG (digit dropped)
    (1004, 2): (0.98, None, []),
    (1008, 2): (0.90, None, ["invoice_number"]),      # missing required field
    (1011, 1): (0.96, None, []),
    (1011, 2): (0.71, "table_row_uncertain", []),
    (1011, 3): (0.95, None, []),
    (1013, 1): (0.64, "merged_cells_suspected", []),
    (1013, 2): (0.58, "chart_not_detected", []),
    (1015, 1): (0.55, "rotated_scan", ["applicant"]),
    (1015, 2): (0.62, "rotated_scan", []),
    (1015, 3): (0.70, "rotated_scan", []),
    (1016, 1): (0.95, None, []),                      # CONFIDENT BUT WRONG (footnote lost)
    (1016, 2): (0.93, None, []),                      # CONFIDENT BUT WRONG (reading order)
    (1021, 1): (0.74, "table_boundary_uncertain", []),
}

jobs, batches = [], []
for b in range(5):
    batches.append({"batch_id": f"BATCH-{b + 1:02d}", "customer": CUSTOMERS[b],
                    "parser_version": "v2.0", "job_ids": [], "status": "", "pages": []})

for n in range(1001, 1031):
    batch = batches[(n - 1001) // 6]
    doc_type, pages = SPEC.get(n) or (rng.choice(list(DOC_TYPES)), rng.randint(2, 5))
    expected = DOC_TYPES[doc_type]["expected_sec_per_page"] * pages
    job = {"job_id": f"JOB-{n}", "batch_id": batch["batch_id"], "customer": batch["customer"],
           "doc_type": doc_type, "pages": pages, "status": "completed",
           "parser_version": "v2.0", "submitted_at": f"2026-10-0{rng.randint(1, 5)}T0{rng.randint(6, 9)}:{rng.randint(10, 59)}:00Z",
           "duration_sec": round(expected * rng.uniform(0.8, 1.3)), "errors": []}
    if n == 1009:
        job.update(status="failed", duration_sec=None,
                   errors=["TIMEOUT_OCR: OCR step exceeded 120s on page 2"])
    elif n == 1017:
        job.update(status="processing", duration_sec=None, elapsed_sec=1900)   # stuck
    elif n == 1028:
        job.update(status="processing", duration_sec=None, elapsed_sec=25)     # healthy
    elif n == 1026:
        job.update(status="queued", duration_sec=None)
    jobs.append(job)
    batch["job_ids"].append(job["job_id"])
    if job["status"] == "completed":
        for p in range(1, pages + 1):
            conf, issue, missing = QUALITY_OVERRIDES.get(
                (n, p), (round(rng.uniform(0.90, 0.99), 2), None, []))
            batch["pages"].append({"job_id": job["job_id"], "page": p, "confidence": conf,
                                   "issue_type": issue, "missing_fields": missing})

status_by_id = {j["job_id"]: j["status"] for j in jobs}
for batch in batches:
    sts = {status_by_id[j] for j in batch["job_ids"]}
    batch["status"] = ("in_progress" if sts & {"processing", "queued"}
                       else "completed_with_failures" if "failed" in sts else "completed")

# --------------------------------------------------------------------------
# Source vs parsed page pairs (for compare_source_vs_parsed)
# --------------------------------------------------------------------------
pair_rng = random.Random(11)
pages_data = {}


def add_pair(job, page, doc_type, *injectors):
    src = BUILDERS[doc_type](pair_rng)
    pages_data[f"JOB-{job}:{page}"] = {"source": src, "parsed": faulty(src, *injectors)}


add_pair(1004, 1, "invoice", inj_value)            # confident but wrong
add_pair(1004, 2, "invoice")                       # clean
add_pair(1011, 2, "bank_statement", inj_missing_row)
add_pair(1011, 3, "bank_statement")                # clean
add_pair(1013, 1, "financial_report", inj_merge)
add_pair(1013, 2, "financial_report", inj_drop_chart)
add_pair(1016, 1, "research_paper", inj_drop_footnote)   # confident but wrong
add_pair(1016, 2, "research_paper", inj_swap)            # confident but wrong

# --------------------------------------------------------------------------
# Regression samples: same documents parsed by two parser versions
# 3 regressions (REG-003, 006, 008) and 2 improvements (REG-002, 009)
# --------------------------------------------------------------------------
reg_rng = random.Random(23)
REG_PLAN = [  # (doc_type, v1.4 injectors, v2.0 injectors)
    ("invoice", [], []),
    ("bank_statement", [inj_missing_row], []),        # improved
    ("invoice", [], [inj_value]),                     # regressed
    ("financial_report", [], []),
    ("research_paper", [], []),
    ("financial_report", [], [inj_drop_chart]),       # regressed
    ("bank_statement", [], []),
    ("financial_report", [], [inj_merge]),            # regressed
    ("research_paper", [inj_swap], []),               # improved
    ("invoice", [], []),
]
regression = {}
for i, (dt, old_inj, new_inj) in enumerate(REG_PLAN, start=1):
    src = BUILDERS[dt](reg_rng)
    regression[f"REG-{i:03d}"] = {"doc_type": dt, "source": src,
                                  "outputs": {"v1.4": faulty(src, *old_inj),
                                              "v2.0": faulty(src, *new_inj)}}

# --------------------------------------------------------------------------
for name, obj in [("document_types.json", DOC_TYPES), ("jobs.json", jobs),
                  ("batches.json", batches), ("pages.json", pages_data),
                  ("regression_samples.json", regression)]:
    with open(os.path.join(DATA, name), "w") as f:
        json.dump(obj, f, indent=1)
print(f"Wrote {len(jobs)} jobs, {len(batches)} batches, {len(pages_data)} page pairs, "
      f"{len(regression)} regression samples to {DATA}")
