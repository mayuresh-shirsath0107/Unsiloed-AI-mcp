# Failure Report FR-014: Merged or Split Table Cells
*Mock internal document for demo purposes.*
**Severity:** High. **Affects:** financial_report, invoice. **First seen:** parser v1.2.

## Symptoms
Customers report that two neighbouring columns in a table arrive as one cell, or that one cell is split in two. The row then has fewer or more cells than the header. Downstream spreadsheets shift values one column to the left, so totals land in the wrong column. The parser usually gives the page a low confidence (0.55 to 0.70) with the flag merged_cells_suspected, but not always.

## Root cause
The table detector decides column boundaries from vertical ruling lines and from whitespace gaps. When a table has no visible lines, which is common in financial reports exported from accounting tools, and two numeric columns are separated by a narrow gap, the whitespace heuristic treats the gap as the inside of a cell. A second trigger is a right-aligned numeric column placed directly next to a left-aligned text column.

## How to detect
1. Run check_batch_quality and look for the merged_cells_suspected flag.
2. Run compare_source_vs_parsed on the page. A cell_structure_changed difference such as "expected 4 cells, got 3" confirms the issue.
3. Check whether the original table has ruling lines. No lines plus narrow gaps is the classic pattern.

## Fix
- Reprocess the page with table_mode=whitespace_strict, which requires a wider gap before splitting columns.
- If the table has no header row, supply expected_columns so the detector knows the column count.
- Since parser v1.5 a post-processing step re-splits cells using header alignment. Confirm the batch used v1.5 or newer.
- For urgent deliveries, correct the affected rows by hand and mark the job as manually reviewed.

## Customer reply template
"We found that two columns in table N on page P were merged during extraction. We reprocessed the page with stricter column detection and the corrected output is attached. No other pages were affected."

## Past incidents
- 2026-03: Northwind Capital quarterly report, 14 pages, 3 tables affected. Fixed with table_mode=whitespace_strict.
- 2026-06: Helix Logistics invoices, about 40 documents. A new invoice template had narrow column gaps.
- 2026-08: Recurrence on one layout after the v2.0 rollout. The layout was added to the regression samples.
