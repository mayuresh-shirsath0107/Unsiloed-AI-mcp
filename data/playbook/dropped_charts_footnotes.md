# Failure Report FR-027: Dropped Charts, Figures and Footnotes
*Mock internal document for demo purposes.*
**Severity:** Medium. **Affects:** financial_report, research_paper. **First seen:** parser v1.4.

## Symptoms
The parsed output contains the text and tables of a page but a chart, a figure caption, or the footnotes at the bottom are missing. Customers notice when a downstream summary cites a figure that does not exist in the data, or when a footnote that qualifies a number, such as "figures in USD thousands", is gone. Confidence may be low with chart_not_detected, but footnote loss usually comes with high confidence, so the parser does not warn.

## Root cause
Charts: the chart detector requires a minimum size and contrast. Vector charts embedded as drawing commands, with no raster image, can be skipped when the detector only looks at images.
Footnotes: small text under about 7 pt near the bottom margin is cropped by the margin filter that removes page numbers and running footers.

## How to detect
1. For charts, check_batch_quality may show chart_not_detected.
2. For both, compare_source_vs_parsed reports chart_missing or footnote_missing. This is the only reliable way to find silent footnote loss.
3. Spot check any financial report where numbers carry units or qualifiers.

## Fix
- Reprocess with chart_mode=vector_aware to include vector drawings.
- Lower the footer margin with footer_margin=minimal so small footnotes are kept. Page numbers may then appear in the output, which is acceptable.
- Since parser v1.6, footnote detection looks for superscript markers in the body text and keeps matching lines. Check that the batch used v1.6 or newer.

## Customer reply template
"We found that a chart on page P and the footnote on page Q were not extracted. They are now included in the attached output. We have also added a check for this pattern to our delivery process."

## Past incidents
- 2026-04: Northwind Capital annual report, 6 vector charts dropped.
- 2026-07: Research paper batch for an academic publisher, footnotes lost on about 30 percent of pages.
- 2026-09: One unit footnote ("USD thousands") lost on a financial summary. The customer caught it after a 1000x error in their report.
