# Failure Report FR-021: Rotated or Skewed Scanned Pages
*Mock internal document for demo purposes.*
**Severity:** High. **Affects:** scanned_form, occasionally invoice. **First seen:** parser v1.0.

## Symptoms
Extracted text is gibberish or empty, fields such as applicant name or form ID come back missing, and the page confidence is very low (0.50 to 0.70) with the flag rotated_scan. Customers usually notice because a whole form returns with every field blank.

## Root cause
Scans from office copiers and phone cameras are often rotated by 90 or 180 degrees, or skewed by several degrees. The OCR stage assumes upright text. Orientation detection fails when a page is mostly a table or a form grid with little running text, because there is not enough text to infer the direction. Low resolution below 150 DPI makes this worse.

## How to detect
1. check_batch_quality flags rotated_scan or confidence below 0.70 on consecutive pages of the same job.
2. The parsed output contains many non-dictionary tokens or repeated single characters.
3. The job metadata shows a scan resolution below 150 DPI.

## Fix
- Reprocess with auto_orient=true and deskew=true. This resolves most cases.
- If the resolution is below 150 DPI, upscale before OCR, and tell the customer that quality depends on the source scan.
- For forms with a known template, pass template_id so orientation is inferred from the printed form layout instead of the text.
- Pages that still fail should go to manual review, not be delivered.

## Customer reply template
"Pages P to Q of your batch were scanned sideways, which caused extraction to fail. We reprocessed them with automatic rotation and the results are attached. For best accuracy, please scan at 200 DPI or higher."

## Past incidents
- 2026-02: Brightpath Health intake forms, 120 pages rotated 180 degrees by a single scanner.
- 2026-05: Ardent Legal affidavits scanned by phone, skew up to 12 degrees.
- 2026-09: Kestrel Insurance claim forms at 100 DPI. Upscaling improved fields but the customer was asked to rescan.
