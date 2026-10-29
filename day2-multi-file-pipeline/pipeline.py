"""
Day 2 - Multi-File Data Processing Pipeline
Soko Fresh Supermarkets - nightly till exports

Usage:  python pipeline.py --input data/ --output output/
"""
import argparse
import csv
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS: set[str] = {
    "transaction_id", "date", "branch", "customer_id",
    "product", "quantity", "unit_price", "payment_method",
}

# The POS upgrade renamed "quantity" to "qty". Only documented aliases are mapped;
# a header still missing a required column afterwards rejects the whole file.
# Decision justified in README.md.
COLUMN_ALIASES: dict[str, str] = {"qty": "quantity"}

# Columns that must hold positive whole numbers (a set: the cleaning stage loops over it).
NUMERIC_COLUMNS: set[str] = {"quantity", "unit_price"}

# Exact output layout from the expected-output resource, including source_file.
CONSOLIDATED_COLUMNS: list[str] = [
    "transaction_id", "date", "branch", "customer_id", "product",
    "quantity", "unit_price", "line_total", "payment_method",
    "payment_ref", "source_file",
]

# Rejection reasons are prefixed with one of these keys, which maps to a summary counter.
REASON_CATEGORIES: set[str] = {"missing value", "invalid number", "duplicate transaction_id"}


def discover_files(folder: Path, pattern: str = "transactions_*.csv") -> list[Path]:
    """Return the matching CSV files in a stable (date) order using pathlib."""
    
    discovered = []

    if not folder.is_dir():
        logger.warning('Input folder does not exist')
    for path in folder.glob(pattern):
        if path.is_file():
            discovered.append(path) # add path to discovered

    # sorting the files using dates
    discovered.sort(key=lambda x: datetime.strptime(x.stem.split('_')[1].replace('.csv', ''), "%Y-%m-%d"))
    logger.info('Files discovered and sorted')
    return discovered


def read_transactions(path: Path) -> tuple[list[str], list[dict]]:
    """Read one file and return (header, rows). Every row remembers its source file and line number."""
    with path.open("r", newline="", encoding="utf-8-sig") as handle:  # utf-8-sig survives a BOM
        reader = csv.DictReader(handle)
        header = [name.strip() for name in (reader.fieldnames or [])]
        rows: list[dict] = []
        for line_number, raw_row in enumerate(reader, start=2):  # line 1 is the header
            row: dict = {}
            for key, value in raw_row.items():
                if key is None:  # a row longer than the header: drop the unnamed extras
                    continue
                row[key.strip()] = "" if value is None else value  # short rows give None
            row["source_file"] = path.name
            row["line_number"] = line_number
            rows.append(row)
    return header, rows


def validate_columns(header: list[str], required: set[str] = REQUIRED_COLUMNS) -> set[str]:
    """Return the set of required columns missing from the header (empty set means valid)."""
    present = {column.strip() for column in header}
    return set(required) - present  # set difference IS "what is missing"


def apply_aliases(header: list[str], rows: list[dict]) -> tuple[list[str], list[dict]]:
    """Rename documented alias columns (e.g. qty -> quantity) in the header and every row."""
    renames: dict[str, str] = {}
    for column in header:
        target = COLUMN_ALIASES.get(column)
        if target and target not in header and target not in renames.values():
            renames[column] = target
    if not renames:
        return header, rows
    new_header = [renames.get(column, column) for column in header]
    new_rows = [{renames.get(key, key): value for key, value in row.items()} for row in rows]
    logger.info("mapped column alias %s", ", ".join(f"{old!r} -> {new!r}" for old, new in renames.items()))
    return new_header, new_rows


def _to_int(value: str) -> int:
    """Parse a CSV number field into an int; raise ValueError when it is not a whole number."""
    text = value.strip()
    try:
        return int(text)
    except ValueError:
        pass
    number = float(text)  # raises ValueError for 'two'
    if not number.is_integer():
        raise ValueError(f"{text!r} is not a whole number")
    return int(number)


def find_problems(row: dict, seen_ids: set[str]) -> list[str]:
    """Return a list of human-readable reasons this row is invalid (empty list means valid).

    Covers: blank required values, non-numeric or non-positive quantity/price,
    and transaction IDs already accepted earlier in this run (including earlier files).
    A row can collect more than one reason.
    """
    problems: list[str] = []

    # 1. blank required values - checked first so a blank is "missing", not "invalid"
    blank_columns: set[str] = set()
    for column in sorted(REQUIRED_COLUMNS):
        value = row.get(column)
        text = "" if value is None else str(value).strip()
        if text == "":
            problems.append(f"missing value: {column} is blank")
            blank_columns.add(column)

    # 2. quantity / unit_price must parse as whole numbers greater than zero
    for column in sorted(NUMERIC_COLUMNS):
        if column in blank_columns:
            continue  # already reported as a missing value - do not double-count
        text = str(row.get(column) or "").strip()
        try:
            number = _to_int(text)
        except ValueError:
            problems.append(f"invalid number: {column} = {text!r} is not a whole number")
            continue
        if number <= 0:
            problems.append(f"invalid number: {column} = {number} must be greater than 0")

    # 3. duplicate transaction IDs anywhere in this run (earlier rows and earlier files)
    transaction_id = str(row.get("transaction_id") or "").strip()
    if transaction_id and transaction_id in seen_ids:
        problems.append(f"duplicate transaction_id: {transaction_id} already accepted in this run")

    return problems


# --------------------------------------------------------------------------- step 5
def clean_row(row: dict) -> dict:
    """Return a normalised copy of a valid row (whitespace stripped, numbers as int, line_total added)."""
    cleaned = {
        key: value.strip() if isinstance(value, str) else value
        for key, value in row.items()                      # dict comprehension
    }
    for column in NUMERIC_COLUMNS:                         # loop over a set
        cleaned[column] = _to_int(str(cleaned.get(column, "")))
    cleaned["line_total"] = cleaned["quantity"] * cleaned["unit_price"]
    return cleaned


# --------------------------------------------------------------------------- steps 6/7
def write_csv(rows: list[dict], path: Path, fieldnames: list[str]) -> None:
    """Write rows to CSV, creating parent folders as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def record_rejection(row: dict, reasons: list[str], rejected: list[dict],
                     extra_columns: list[str]) -> None:
    """Build one rejected record (provenance + all reasons joined) and track the columns seen."""
    record = {
        "source_file": row.get("source_file", ""),
        "row_number": row.get("line_number", ""),
        "transaction_id": str(row.get("transaction_id") or "").strip(),
        "reasons": "; ".join(reasons),
    }
    for key, value in row.items():
        if key in ("source_file", "line_number", "transaction_id", "reasons"):
            continue
        record[key] = value
        if key not in extra_columns:  # union of original columns across files, stable order
            extra_columns.append(key)
    rejected.append(record)


# --------------------------------------------------------------------------- step 8
def build_summary(stats: dict) -> str:
    """Format the processing summary shown in the expected-output resource."""
    lines: list[str] = ["=== Processing summary ==="]

    def add(label: str, value) -> None:
        lines.append(f"{label:<25}{value}")  # labels are padded to column 25

    add("Files discovered:", stats["files_discovered"])
    add("Files processed:", stats["files_processed"])
    issues = stats["column_issues"]
    if issues:
        detail = "; ".join(
            f"{issue['file']}: missing {', '.join(issue['missing'])} [{issue['resolution']}]"
            for issue in issues
        )
        add("Files with column issues:", f"{len(issues)}  ({detail})")
    else:
        add("Files with column issues:", 0)
    add("Rows read:", stats["rows_read"])
    add("Rows accepted:", stats["rows_accepted"])
    add("Rows rejected:", stats["rows_rejected"])
    add("  - missing values:", stats["missing_values"])
    add("  - invalid numbers:", stats["invalid_numbers"])
    add("  - duplicate IDs:", stats["duplicate_ids"])
    add("Total revenue (KES):", stats["total_revenue"])
    add("Run finished at:", stats["finished_at"])
    return "\n".join(lines)


def run_pipeline(input_dir: Path, output_dir: Path) -> dict:
    """Run every step and return the statistics used by build_summary()."""
    files = discover_files(input_dir)

    accepted: list[dict] = []
    rejected: list[dict] = []
    seen_ids: set[str] = set()        # IDs accepted so far, shared across every file
    extra_columns: list[str] = []     # union of original columns for the rejected report
    column_issues: list[dict] = []
    reason_counts = {category: 0 for category in REASON_CATEGORIES}
    rows_read = 0
    files_processed = 0

    for path in files:
        header, rows = read_transactions(path)
        rows_read += len(rows)

        raw_header = list(header)
        raw_missing = validate_columns(header)      # before alias mapping
        header, rows = apply_aliases(header, rows)
        missing = validate_columns(header)          # after alias mapping

        if missing:
            # Unknown/missing column: reject the whole file - every row keeps a reason.
            column_issues.append({
                "file": path.name,
                "missing": sorted(missing),
                "resolution": "whole file rejected",
            })
            reason = f"file rejected: missing required columns: {', '.join(sorted(missing))}"
            for row in rows:
                record_rejection(row, [reason], rejected, extra_columns)
            logger.warning("%s: %s", path.name, reason)
            continue

        if raw_missing:
            # every raw gap was closed by a documented alias (otherwise we would have continued)
            mapped = ", ".join(
                f"{old} -> {COLUMN_ALIASES[old]}"
                for old in sorted(raw_header)
                if old in COLUMN_ALIASES and COLUMN_ALIASES[old] in raw_missing
            )
            column_issues.append({
                "file": path.name,
                "missing": sorted(raw_missing),
                "resolution": f"alias mapped ({mapped})" if mapped else "resolved",
            })

        files_processed += 1
        file_accepted = 0
        for row in rows:
            problems = find_problems(row, seen_ids)
            if problems:
                record_rejection(row, problems, rejected, extra_columns)
            else:
                cleaned = clean_row(row)
                seen_ids.add(cleaned["transaction_id"])  # only accepted IDs reserve their ID
                accepted.append(cleaned)
                file_accepted += 1
            # count each reason category at most once per rejected row (set comprehension)
            for category in {problem.split(":", 1)[0] for problem in problems}:
                if category in reason_counts:
                    reason_counts[category] += 1
        logger.info("%s: read %d, accepted %d, rejected %d",
                    path.name, len(rows), file_accepted, len(rows) - file_accepted)

    # Invariant: nothing that was read may silently disappear.
    if len(accepted) + len(rejected) != rows_read:
        raise RuntimeError(
            f"accepted ({len(accepted)}) + rejected ({len(rejected)}) "
            f"!= rows read ({rows_read})"
        )

    write_csv(accepted, output_dir / "consolidated_transactions.csv", CONSOLIDATED_COLUMNS)
    rejected_columns = ["source_file", "row_number", "transaction_id", "reasons"] + extra_columns
    write_csv(rejected, output_dir / "rejected_transactions.csv", rejected_columns)

    stats = {
        "files_discovered": len(files),
        "files_processed": files_processed,
        "column_issues": column_issues,
        "rows_read": rows_read,
        "rows_accepted": len(accepted),
        "rows_rejected": len(rejected),
        "missing_values": reason_counts["missing value"],
        "invalid_numbers": reason_counts["invalid number"],
        "duplicate_ids": reason_counts["duplicate transaction_id"],
        "total_revenue": sum(row["line_total"] for row in accepted),
        "finished_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }

    summary = build_summary(stats)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.txt").write_text(summary + "\n", encoding="utf-8")
    return stats


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(
        description="Discover, validate, clean and consolidate Soko Fresh daily till exports."
    )
    parser.add_argument("--input", type=Path, default=Path("data"),
                        help="folder holding transactions_*.csv files (default: data/)")
    parser.add_argument("--output", type=Path, default=Path("output"),
                        help="folder for the generated reports (default: output/)")
    parser.add_argument("--log-level", default="WARNING",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="console log level; INFO shows per-file progress (default: WARNING)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=args.log_level, format="%(levelname)s: %(message)s")
    stats = run_pipeline(args.input, args.output)
    print(build_summary(stats))
    return stats


if __name__ == "__main__":
    main()
