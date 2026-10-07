# Failure Report FR-018: Wrong Reading Order in Multi-Column Layouts
*Mock internal document for demo purposes.*
**Severity:** Medium. **Affects:** research_paper, financial_report with sidebars. **First seen:** parser v1.3.

## Symptoms
All the text is present, but paragraphs appear in the wrong sequence. A sentence from the right column continues into the left column, or a sidebar is inserted in the middle of the main text. Language models reading the output produce confused summaries. Confidence is normally high (0.90 or more), so the problem is silent.

## Root cause
The layout analysis orders blocks by vertical position and then horizontal position. In a two-column page, blocks at similar heights in different columns interleave. Pull quotes and sidebars with a different baseline make it worse. Pages where one column is shorter than the other are the most affected.

## How to detect
1. compare_source_vs_parsed reports reading_order_changed, with the positions of the swapped blocks.
2. check_batch_quality will usually not flag it.
3. Spot check any research paper or report with two or more columns.

## Fix
- Reprocess with reading_order=column_aware, which groups blocks by column before sorting.
- For pages with sidebars, set sidebar_mode=separate so sidebars are returned as their own blocks, not inline.
- Parser v1.7 and newer use a learned reading-order model. Check the version of the affected batch.

## Customer reply template
"On page P the text from two columns was read in the wrong order. We reprocessed the page with column-aware ordering and attached the corrected output. All other pages in the batch were checked."

## Past incidents
- 2026-03: Academic publisher batch, 800 two-column pages affected before detection.
- 2026-06: Annual report with a full-height sidebar, text interleaved on every page.
- 2026-09: One research paper layout regressed after the v2.0 upgrade. Added to regression samples.
