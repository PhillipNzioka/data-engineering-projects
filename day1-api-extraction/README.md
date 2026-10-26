# Day 1 - API Data Extraction and Transformation

Day 1 of this project includes the fetching of user data from the JSONPlaceholder REST API, flattens the nested JSON structure dynamically, and exports it as a clean CSV ready for analysis.

## Approach & Assumptions

1. **Error Handling (`fetch_users`)**: 
   - Used `try/except` blocks to catch `ConnectionError`, `Timeout`, and invalid JSON.
   - Checked `response.status_code == 200` before attempting to parse the body.
   - On failure, the script prints a clear error message and uses `sys.exit(1)` to terminate gracefully without a raw traceback.
2. **Structure Description (`describe_structure`)**: 
   - Iterated through the first record's items. Checked for `dict` instances to identify nested keys (e.g., `address`, `geo`, `company`) and printed their types.
3. **Missing Fields (`extract_core_fields`)**: 
   - Assumption: If a nested field (like `city` or `company_name`) is missing, it defaults to `"Unknown"` using chained `.get()` methods instead of failing.
4. **Flattening (`flatten_user`)**: 
   - Used a recursive function to handle any depth of nesting. Keys are joined with underscores (`_`). This ensures it works for new, unseen nested data.
5. **DataFrame & Export (`to_dataframe` & `export_csv`)**: 
   - Cast `address_geo_lat` and `address_geo_lng` to floats.
   - Renamed `id` to `customer_id`.
   - Ensured the output directory is created if it doesn't exist. Used `to_csv(index=False)` to avoid the pandas index column in the output.

## Day 1 workflow

The first project follows a simple but important data engineering flow:

1. Fetch data from the API.
2. Check that the request succeeded.
3. Validate the response body.
4. Inspect the structure of the records.
5. Pull the required customer information.
6. Flatten nested fields such as address and company details.
7. Convert the output to a pandas DataFrame.
8. Save the final result as a CSV.

## Skills demonstrated

This project shows a useful set of core data engineering capabilities:

- API extraction
- Data validation
- Handling nested JSON
- Recursive flattening
- Data cleaning and normalization
- Pandas-based transformation
- CSV output for analytics use cases

## Quick start

From the project root, run:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python extract_customers.py
```

The output file is generated here:

```text
day1-api-extraction/output/customers_clean.csv
```
