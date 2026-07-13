# Bank Ledger Classification Owner Evidence Packet

## Current decision state

- Page: `PAGE-BANK-LEDGER-001` / `/bank-ledger-dashboard`.
- Golden sample: `GS-BANK-LEDGER-CLASSIFICATION-A`.
- Golden status: `captured-awaiting-approval`.
- Formal-use status: `formal_use_allowed=false`.
- No owner decision or signature is recorded by this packet.

## Evidence ready for review

- Historical replay: batches 1-8, 14,731 rows, 13,679 `ASSET`, 1,052 `LIABILITY`, zero direction changes.
- Applied rule lineage: `rv_ledger_classification_v2` in batch, raw, and snapshot rows.
- Apply plan digest: `1c90458a94f56525d4ee360cd2e7cad6fe79f035508b89355f0fd795fa6f065c`.
- Completed receipt: `data/receipts/ledger-classification-v2-20260712-1c90458a-retry1.json`.
- Restore point: `data/backups/moss-before-ledger-classification-v2-20260712-1c90458a.duckdb`.
- Immutable evidence and `position_snapshot_agg` matched the restore point after apply.
- Dedicated fixture freezes five asset pairs, one liability pair, and missing/unknown/conflict fail-closed behavior.

## Decisions required from the business owner

1. Accept or reject each of the five `ASSET` allowlist pairs.
2. Accept or reject `(发行类债券, 发行类债券) -> LIABILITY`.
3. Confirm that missing, unknown, and conflicting pairs remain `UNCLASSIFIED` rather than being guessed.
4. Confirm row-based classification coverage and the exclusion of `UNCLASSIFIED` amounts from asset, liability, and net exposure.
5. Confirm amounts remain native currency divided by 100 million, with no cross-currency addition or FX conversion.
6. Review authorized real-page UAT evidence for ready, stale/fallback, no-data, currency selection, and detail drill-down states.

## Release boundary

- Technical replay and a capture-ready sample do not constitute owner approval.
- Do not change `formal_use_allowed=false` until the approval template has non-placeholder identities, decision, date, and signature, and authorized UAT evidence is attached.
