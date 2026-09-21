# Changelog

## 0.5.2

- Accept comma-, newline-, and semicolon-separated lists in multiple-value text and lookup fields. Lookup lists are checked together before adding, and duplicate values are removed.
- Keep lookup suggestions inside the form layout so results are not clipped at the bottom of a panel.
- Allow `local=true` and `local=false` before or after the inputlookup name.
- Reduce lookup overhead by skipping occupied rate-limit slots, waiting for search completion during dispatch, and caching recent suggestions for 30 seconds. Submission still revalidates lookup values.

## 0.5.1

- Set `is_configured = false` in the distributed app configuration.
- Declare `python.version = python3.9` for the REST handler while retaining `python.required = 3.9, 3.13`.
- Check these settings during packaging.
