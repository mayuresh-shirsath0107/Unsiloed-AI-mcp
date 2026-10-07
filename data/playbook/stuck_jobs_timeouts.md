# Failure Report FR-031: Stuck Jobs and OCR Timeouts
*Mock internal document for demo purposes.*
**Severity:** High. **Affects:** all document types, mostly scanned_form and large financial_report files. **First seen:** parser v1.5.

## Symptoms
A job stays in processing far longer than normal, or fails with TIMEOUT_OCR. Customers write to ask whether their job is done. A batch cannot be delivered because one job never finishes. The job status tool warns when the elapsed time is more than three times the expected time for that document type and page count.

## Root cause
Three common causes: very large page images above about 25 megapixels, which push OCR past the 120 second per-page limit; worker queue starvation right after a deployment, when workers restart and jobs wait; and corrupted PDF pages that make the renderer loop. Jobs with many pages and high resolution scans combine all three risks.

## How to detect
1. get_parse_job shows status processing with elapsed time far above expected, or an error such as TIMEOUT_OCR.
2. Several stuck jobs at the same time right after a deploy point to queue starvation, not to the documents.
3. Check page size in the job metadata. Pages above 25 megapixels are the likely cause for single jobs.

## Fix
- Cancel the job and resubmit with max_image_mp=20, which downsizes oversized pages before OCR.
- For suspected corrupted pages, split the document and process pages separately to isolate the bad page.
- If more than five jobs are stuck, escalate to the platform on-call: restart the worker pool and requeue.
- Tell the customer the expected completion time after resubmitting.

## Customer reply template
"Your job was delayed because one page was unusually large. We resubmitted it with optimized settings and expect results within N minutes. We will confirm when the batch is complete."

## Past incidents
- 2026-02: Brightpath Health, 40 scans at 600 DPI exceeded the OCR time limit.
- 2026-06: Deployment left 17 jobs queued for 25 minutes, resolved by restarting the worker pool.
- 2026-09: One financial report with a corrupted page blocked a batch for three hours.
