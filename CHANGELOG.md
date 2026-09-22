# Changelog

## 0.5.3

- Query simple KV Store lookups directly instead of dispatching search jobs. Preserve SPL execution for transformations, filtered definitions, and multivalue expansion.
- Match pasted lookup values without regard to case, remove case-only duplicates, and send the stored lookup values to SOAR.
- Show playbook and action totals with status counts on ten-row submission pages. Refresh only the current page.
- Use custom action run names in receipts. Include reported format, filter, decision, code, and utility results; show unknown when SOAR does not report a block status.
- Enable SOAR automation by default for new forms and add Scan, Server, and User icons. Existing and cloned forms retain their automation setting.
- Group field types and configuration into collapsible sections. Keep navigation visible while scrolling and prevent profile avatars from shrinking into ovals.

## 0.5.2

- Add static text to the form builder with plain, information, and warning styles and conditional visibility.
- Accept comma-, newline-, and semicolon-separated lists in multiple-value text and lookup fields. Lookup lists are checked together before adding, and duplicate values are removed.
- Keep lookup suggestions inside the form layout so results are not clipped at the bottom of a panel.
- Allow `local=true` and `local=false` before or after the inputlookup name.
- Reduce lookup overhead by skipping occupied rate-limit slots, waiting for search completion during dispatch, and caching recent suggestions for 30 seconds. Submission still revalidates lookup values.

## 0.5.1

- Set `is_configured = false` in the distributed app configuration.
- Declare `python.version = python3.9` for the REST handler while retaining `python.required = 3.9, 3.13`.
- Check these settings during packaging.
