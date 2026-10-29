# Soko Fresh daily till export pipeline

Each night every branch (Nairobi, Mombasa, Kisumu, Nakuru) drops a CSV of the day's sales into a shared folder. The pipeline finds every `transactions_*.csv` file, checks its columns and rows, and cleans the rows it can trust. It writes two CSVs, one of accepted rows and one of rejected rows with a reason for each, then prints a summary that reconciles against both.

## Run it

```bash
python pipeline.py --input data/ --output output/
```

Options: `--input` (default `data/`), `--output` (default `output/`), and `--log-level INFO` for per-file progress lines.

The pipeline uses only the standard library (`pathlib`, `csv`, `argparse`, `logging`, `datetime`). It does not use pandas.

## Outputs

| File | Contents |
|---|---|
| `output/consolidated_transactions.csv` | 34 accepted rows. Columns: `transaction_id,date,branch,customer_id,product,quantity,unit_price,line_total,payment_method,payment_ref,source_file` |
| `output/rejected_transactions.csv` | 9 rejected rows. Columns: `source_file,row_number,transaction_id,reasons`, then the union of the original columns (`cashier` appears here) |
| `output/summary.txt` | The text the program prints (the `=== Processing summary ===` block) |

With the sample data, 43 rows read = 34 accepted + 9 rejected (4 missing values, 2 invalid numbers, 3 duplicate IDs). Total revenue is KES 22,775.

## Decisions

### 1. A known alias is mapped; any other missing column rejects the file

The POS upgrade renamed `quantity` to `qty`. One line records the rename:

```python
COLUMN_ALIASES: dict[str, str] = {"qty": "quantity"}
```

`run_pipeline` checks the header twice: once as is, and once after `apply_aliases` rewrites each documented alias in the header and in every row.

Why map a known alias? It is a rename, not a schema change, and rejecting the file would drop a whole day of good sales from finance's reports over one header word. Mapping keeps the data moving. The summary still lists the event as a column issue, so the branches can be told their exporter changed.

Why reject anything else? A guess at an unknown column can map data wrongly: `price` might be `unit_price`, or it might be the line total. If a required column is still missing after alias mapping, the file's structure can't be trusted. Every row of that file goes to `rejected_transactions.csv` with the reason `file rejected: missing required columns: …`. Nothing disappears, and finance can see which file to chase.

### 2. Duplicates: only accepted rows reserve their ID

`seen_ids` is a `set` that lasts the whole run, across files, in file-date order. The pipeline adds an ID when it accepts a row, not when it reads one.

This catches a retry that re-sends yesterday's transactions, because an earlier file already had those IDs accepted: `duplicate transaction_id: TXN-1012 already accepted…`.

A rejected row, such as one with a blank `unit_price`, does not reserve its ID. If the branch sends a corrected version tomorrow, the pipeline can accept it. Reserving rejected IDs would block the fix and lose good data.

Each ID therefore appears once in the consolidated file. We checked: `consolidated_transactions.csv` has 0 duplicate IDs.

### 3. Row numbers are physical CSV lines (header = line 1)

`read_transactions` enumerates rows with `start=2`, so `row_number` in the rejected report matches the line finance sees in Excel. They can go straight to it.

### 4. Blank and invalid differ, and a row can have several reasons

`find_problems` collects a list of reasons and does not stop at the first. It checks in this order:

1. Blank required values give `missing value: …`.
2. Bad numbers give `invalid number: …`. This check skips columns already reported as blank, so an empty `quantity` counts once as missing and never also as invalid.
3. Repeated IDs give `duplicate transaction_id: …`.

`"two"` and `-4` are both rejected, for different reasons. `"two"` fails to parse. `-4` parses but fails the `> 0` check.

### 5. Summary counts are per row

`missing values`, `invalid numbers` and `duplicate IDs` each count the rejected rows that have at least one reason of that type. A row with reasons in two categories counts in both. In the sample data every rejected row has one category, so 4 + 2 + 3 = 9, which equals `Rows rejected`.

### 6. The reconciliation check runs on every run

Before it writes anything, `run_pipeline` raises an error if `accepted + rejected != rows read`. With the current data, 34 + 9 = 43, and `data/*.csv` holds the same 43 rows.

## How each step maps to the code

| Step | Function(s) | Concept |
|---|---|---|
| 1 Read files | `read_transactions` | `csv.DictReader`, `newline=""`, BOM-safe encoding, provenance per row |
| 2 Discover | `discover_files` | `Path.glob`, sorted by date parsed from the filename |
| 3 Columns | `validate_columns`, `apply_aliases` | set difference `required - header`, alias dictionary |
| 4 Problems | `find_problems`, `_to_int` | accumulating list, blank vs invalid, `seen_ids` set |
| 5 Clean | `clean_row` | dict comprehension, loop over the `NUMERIC_COLUMNS` set, `line_total` |
| 6 Combine | `write_csv` + `CONSOLIDATED_COLUMNS` | `DictWriter`, dedup via `seen_ids` |
| 7 Reject | `record_rejection` | provenance + `"; ".join(reasons)`, column union across files |
| 8 Summary | `build_summary`, `run_pipeline` | stats dict, f-string padding to column 25, reconciliation |

## Adding a fourth day's file

Drop `transactions_2026-10-04.csv` into `data/` and re-run. No code changes are needed. The glob finds the file and puts it in date order.