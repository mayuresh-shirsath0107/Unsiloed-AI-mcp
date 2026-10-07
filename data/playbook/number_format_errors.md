# Failure Report FR-009: Wrong Digits and Number Formats
*Mock internal document for demo purposes.*
**Severity:** Critical. **Affects:** invoice, bank_statement, financial_report. **First seen:** parser v1.1.

## Symptoms
A number in a table is slightly wrong: a digit is dropped ("1,250.00" becomes "1,25.00"), a decimal point moves, or a European format ("1.250,00") is read as an English one. The page usually gets HIGH confidence (0.95 or more), so no automatic warning appears. These errors are the most dangerous because they flow straight into customer accounting systems.

## Root cause
Digit drops happen on thin fonts, low contrast numerals, and digits that touch table gridlines, where the OCR merges a digit with the line. Separator confusion happens when a document mixes locales or when the locale hint is missing. Total rows in bold or with a top border are especially prone to digit loss.

## How to detect
1. Do not rely on confidence. Run compare_source_vs_parsed and look for value_changed differences.
2. Cross-check arithmetic: sum the line items and compare to the total. A mismatch is a strong signal.
3. Look for numbers whose digit count differs from other values in the same column.

## Fix
- Reprocess the page with the digit-focused recognizer, numeric_mode=strict.
- Set the locale hint (locale=en_US or locale=de_DE) when the customer's documents use a known format.
- Enable the totals validation step, which flags rows whose values do not add up.
- Always have a human confirm corrected amounts on invoices and statements before delivery.

## Customer reply template
"We found a digit error in the total of invoice N, page P. The correct value is X and we have updated the output. We reviewed the other totals in the same batch and found no further errors."

## Past incidents
- 2026-01: Helix Logistics, 3 invoice totals missing one digit after a template change with thin fonts.
- 2026-05: Kestrel Insurance, German-format statements read with swapped separators.
- 2026-08: Northwind Capital, total row digit lost beside a gridline in 11 documents. Found by customer, not by us, which led to the compare-based delivery check.
