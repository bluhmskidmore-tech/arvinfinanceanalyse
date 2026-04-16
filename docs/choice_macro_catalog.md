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
- `fetch_mode`
- `fetch_granularity`
- `refresh_tier`
- `policy_note`
- `series[]`

Each `series[]` entry uses the fields above.

Batch strategy fields mean:

- `fetch_mode`: `date_slice` or `latest`
- `fetch_granularity`: `batch` or `single`
- `refresh_tier`: `stable`, `fallback`, or `isolated`
- `policy_note`: short governance note explaining why the batch sits in that lane

`request_options` is the batch EDB option template. For `date_slice` batches, `StartDate` / `EndDate` may use the `__RUN_DATE__` placeholder so the refresh resolves them at runtime instead of pinning a stale calendar day into source control.

The raw fallback keeps the same batch idea in line form: a `# batch_id ...` comment header followed by one `data=c.edb("code1,code2", "options")` command.

## Loader Precedence

1. If `MOSS_CHOICE_MACRO_CATALOG_FILE` points to an existing file, load the structured catalog first.
2. Otherwise, read `MOSS_CHOICE_MACRO_COMMANDS_FILE` / `config/choice_macro_commands_2026-04-09.txt` as the raw command fallback.
3. Otherwise, fall back to `MOSS_CHOICE_MACRO_SERIES_JSON`.

## Thin Slice Behavior

- The catalog feeds the current EmQuant thin slice only.
- `stable` batches stay on the default refresh path.
- `fallback` batches stay on the default refresh path but can use `latest` + `single` fetches to recover low-frequency series.
- `isolated` batches are cataloged for governance but skipped by the default refresh path until the vendor/API path is confirmed.
- Batches with no data are skipped.
- A skipped batch does not fail the whole refresh run.
- Successful batches are merged, archived, and materialized into the Choice macro DuckDB tables used by the latest preview endpoint.
- The checked-in catalog currently gives all imported series explicit `theme`, `is_core`, and `tags`, but many `frequency` / `unit` fields still need later curation.
