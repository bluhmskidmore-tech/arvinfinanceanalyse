# Choice Macro Catalog

This asset is the structured series catalog for the Choice-first macro thin slice. It tells the refresh job which macro series to fetch, how to group them into batches, and which request options to send to EmQuant.

## Location

- Structured source: `config/choice_macro_catalog.json`
- Raw fallback: `config/choice_macro_commands_2026-04-09.txt`
- Env/test fallback: `MOSS_CHOICE_MACRO_SERIES_JSON`

## Fields

| Field | Meaning |
|---|---|
| `series_id` | Internal canonical series id used across the repo. |
| `series_name` | Human-readable series label. |
| `vendor_series_code` | Choice/EmQuant code sent to the vendor API. |
| `frequency` | Series cadence, carried into the snapshot and fact rows. |
| `unit` | Returned value unit. |
| `theme` | Catalog grouping label for related series. |
| `is_core` | Marks series that belong in the default/core batch set. |
| `tags` | Free-form labels for filtering, review, or alternate batch assembly. |

`theme`, `is_core`, and `tags` are catalog metadata. The current thin slice persists the canonical ids plus `frequency` and `unit`; it does not promote these labels into formal finance logic.

## Batch Shape

Each batch is a JSON object with:

- `batch_id`
- `request_options`
- `series[]`

Each `series[]` entry uses the fields above.

`request_options` is the exact EDB option string for that batch. The runtime still merges in the global Choice request settings before calling EmQuant, and the adapter falls back to `IsPublishDate=1,RowIndex=1,Ispandas=1,RECVtimeout=<timeout>` when a batch leaves it empty.

The raw fallback keeps the same batch idea in line form: a `# batch_id ...` comment header followed by one `data=c.edb("code1,code2", "options")` command.

## Loader Precedence

1. If `MOSS_CHOICE_MACRO_CATALOG_FILE` points to an existing file, load the structured catalog first.
2. Otherwise, read `MOSS_CHOICE_MACRO_COMMANDS_FILE` / `config/choice_macro_commands_2026-04-09.txt` as the raw command fallback.
3. Otherwise, fall back to `MOSS_CHOICE_MACRO_SERIES_JSON`.

## Thin Slice Behavior

- The catalog feeds the current EmQuant thin slice only.
- Batches with no data are skipped.
- A skipped batch does not fail the whole refresh run.
- Successful batches are merged, archived, and materialized into the Choice macro DuckDB tables used by the latest preview endpoint.
- The checked-in catalog currently gives all imported series explicit `theme`, `is_core`, and `tags`, but many `frequency` / `unit` fields still need later curation.
