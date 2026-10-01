# Ops Analytics Lakehouse

**This is a sanitized copy of a project built for a finance & operations analytics team. Company names, data, server details and internal documents have been removed. No data is included, and all data files are gitignored.**

## Project structure

```
.
├── 1_Scripts/
│   ├── pipeline_leadtime.py        # lead-time pipeline entry point
│   ├── pipeline_item_master.py     # item-master pipeline entry point
│   ├── Common/                     # config template, DuckDB connection helper
│   ├── Extract/                    # fetch, Bronze loaders, ERP extract (+ Queries/)
│   └── Transform/                  # Silver generator + Silver/Gold SQL (Queries/)
├── 2_Data_Lakehouse/               # local storage — data files are gitignored
│   ├── 0_Loading_Zone/
│   ├── Master/dim_phase.csv        # hand-maintained phase master
│   └── 3_Gold/                     # Parquet output (created on first run)
├── 3_Documentation/
│   ├── data_catalog.md             # Silver field-level documentation
│   └── git_collaboration_sop.txt   # commit convention and branch workflow
├── requirements.txt
└── setup_environment.bat           # creates a per-machine venv and installs requirements
```

## Overview

A local medallion lakehouse (Bronze → Silver → Gold) on DuckDB. It turns messy quarterly Excel workbooks and an ERP extract into clean, typed Parquet files for Power BI.

**Stack:** Python · DuckDB · pandas · pyodbc (SQL Server) · Power BI (consumer) · DBeaver

---

## Why

Analysts kept the same Excel files in several shared folders, and every Power BI model re-implemented its own cleaning. This project moves the cleaning into one place, with SQL as the single source of truth. Each Power BI report then reads the same Gold tables.

## Architecture

```
Quarterly Excel workbooks ──► 0_Loading_Zone ──► bronze.*  ──► silver.leadtime_data ──► gold.fact_leadtime + dims ──► 3_Gold/*.parquet ──► Power BI
Infor M3 (SQL Server)     ──────────────────────► bronze.m3_item_master ──► silver.item_master ──► gold.dim_item ──► 3_Gold/dim_item.parquet
```

| Layer | Where | What |
|---|---|---|
| Loading zone | `2_Data_Lakehouse/0_Loading_Zone/` | Copies of the source workbooks. Originals are never modified. |
| Bronze | `bronze` schema in `lakehouse.db` | One table per workbook tab, landed as-is, with `_bronze_insert_ts` and `_source_file_name` lineage columns. |
| Silver | `silver` schema | One canonical, deduplicated and typed table per subject. |
| Gold | `gold` schema, exported to `2_Data_Lakehouse/3_Gold/*.parquet` | A star schema for reporting: the lead-time fact and its dimensions, plus the item dimension. |

## Pipelines

### Lead time (`1_Scripts/pipeline_leadtime.py`)
1. `Extract/fetch_source_files.py`: copies matching workbooks from the folders listed in `config.py` into the loading zone.
2. `Extract/load_to_bronze.py`: loads every tab of every workbook into its own Bronze table.
3. `Transform/silver_leadtime.py`: generates and runs the Silver SQL (see below).
4. `Transform/Queries/gold_dim_date.sql` and `gold_leadtime.sql`: build the Gold star schema. Lead-time phases are unpivoted into rows with an MD5 row key. `dim_phase` comes from a hand-maintained CSV, which gives phases a business sort order.
5. Exports each Gold table to Parquet and checks its row count against Gold.

### Item master (`1_Scripts/pipeline_item_master.py`)
1. `Extract/extract_m3_item_master.py`: runs one read-only T-SQL query against Infor M3 standard tables (`MITMAS`, `MITMAH`, `MITAUN`, `MITPOP`, `CSYTAB`, `MITSCH`) and lands every column as text.
2. `silver_item_master.sql`: trims and types every column and enforces one row per SKU.
3. `gold_dim_item.sql`: builds the dimension, with a grain check that fails the run if any SKU repeats.
4. Exports Parquet and, optionally, copies it to other folders.

## Engineering notes

**Schema drift across quarterly workbooks.** The source template changed from quarter to quarter: renamed columns (`whr` → `wh`), typos that were fixed later (`continer_size`), dropped columns and new date formats. Silver is therefore *generated*:
- each target column is resolved from a list of candidate source names;
- dates are parsed with a cascade of formats;
- new quarters are discovered automatically from `information_schema`, by naming pattern and a check for 26 required column groups;
- summary or helper tabs are filtered out;
- older quarters are mapped by hand, with ETD cut-off windows where the files overlap.

**Mislabeled columns in old templates.** The oldest template swapped the min and max ex-factory-to-received columns. The fix keys off the *presence of the old header* (`min_max_xfty`), not a hard-coded list of periods, so any older file that is reloaded still lands correctly.

**Excel zero dates.** A blank date cell is read as 1899-12-30, and the sheet's formula then reports a gap of about 45,900 days. Durations are carried over from the source, but only when both of their endpoint dates actually parse.

**Deduplication.** One row per shipment leg (`wh, asn, folio, b_l, container, etd`), where the latest Bronze load wins. The run warns about NULL `etd` rows, because deduplication could collapse them.

**Read-only ERP access.** The extract may run under a login that can write, so before anything is sent:
- comments and string literals are stripped from the query;
- the query must be a single `SELECT`/`WITH` statement, with no write or DDL keywords;
- the connection uses `autocommit=False`, always rolls back and requests `ApplicationIntent=ReadOnly`;
- every row is read before DuckDB is touched, and an empty result fails the run instead of replacing a good Bronze table.

**Fail-fast orchestration.** Each step runs as a subprocess. A non-zero exit code, or any `WARNING:` line in its output, fails the whole run. Every Parquet export is row-count checked. Copies to export folders are written under a temporary name, validated, then swapped in with `os.replace`, so readers never see a half-written file.

## Getting started

1. **Environment**: run `setup_environment.bat`, or create a venv and `pip install -r requirements.txt`. The item master extract also needs *ODBC Driver 17 for SQL Server*.
2. **Config**: copy `1_Scripts/Common/config_template.py` to `config.py` in the same folder, then fill in the source folders and, for the item master, the M3 connection settings. `config.py` is gitignored.
3. **Run** from the repository root, because the Gold SQL reads `dim_phase.csv` by relative path:
   ```
   python 1_Scripts/pipeline_leadtime.py
   python 1_Scripts/pipeline_item_master.py
   ```

Field definitions are in [3_Documentation/data_catalog.md](3_Documentation/data_catalog.md).
