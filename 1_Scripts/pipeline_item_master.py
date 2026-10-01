from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import duckdb

from pipeline_leadtime import (
    DB_PATH,
    PARQUET_FOLDER,
    ROOT_PATH,
    generate_parquet,
    run_python_step,
)

sys.path.append(str(ROOT_PATH / "1_Scripts" / "Common"))
from config import ITEM_MASTER_EXPORT_FOLDERS


# project paths
EXTRACT_SCRIPT = (
    ROOT_PATH
    / "1_Scripts"
    / "Extract"
    / "extract_m3_item_master.py"
)

SILVER_ITEM_MASTER_SQL = (
    ROOT_PATH
    / "1_Scripts"
    / "Transform"
    / "Queries"
    / "silver_item_master.sql"
)

GOLD_DIM_ITEM_SQL = (
    ROOT_PATH
    / "1_Scripts"
    / "Transform"
    / "Queries"
    / "gold_dim_item.sql"
)

GOLD_TABLES = [
    "dim_item",
]


def run_sql_file(
    con: duckdb.DuckDBPyConnection,
    sql_file: Path,
) -> None:
    if not sql_file.exists():
        raise FileNotFoundError(
            f"SQL file not found: {sql_file}"
        )

    print(f"Running: {sql_file.name}")

    con.execute(
        sql_file.read_text(encoding="utf-8")
    )

    print(f"Completed: {sql_file.name}")


# showing what silver did with the bronze rows
def report_silver(con: duckdb.DuckDBPyConnection) -> None:
    bronze_rows, blank_sku_rows = con.execute(
        """
        SELECT
            COUNT(*),
            COUNT(*) FILTER (WHERE NULLIF(TRIM(sku), '') IS NULL)
        FROM bronze.m3_item_master
        """
    ).fetchone()

    silver_rows = con.execute(
        """
        SELECT COUNT(*)
        FROM silver.item_master
        """
    ).fetchone()[0]

    repeated_skus = con.execute(
        """
        SELECT TRIM(sku) AS sku, COUNT(*) AS row_count
        FROM bronze.m3_item_master
        WHERE NULLIF(TRIM(sku), '') IS NOT NULL
        GROUP BY TRIM(sku)
        HAVING COUNT(*) > 1
        ORDER BY row_count DESC, sku
        """
    ).fetchall()

    print(f"Bronze rows: {bronze_rows:,}")
    print(f"Silver rows (one per SKU): {silver_rows:,}")

    if blank_sku_rows:
        print(f"Dropped {blank_sku_rows:,} row(s) with a blank SKU.")

    if repeated_skus:
        dropped_rows = sum(
            row_count - 1 for _, row_count in repeated_skus
        )

        print(
            f"{len(repeated_skus):,} SKU(s) came back more than once -- "
            f"kept the first row, dropped {dropped_rows:,}. First few:"
        )

        for sku, row_count in repeated_skus[:10]:
            print(f"  {sku}: {row_count} rows")

    else:
        print("OK: every SKU came back exactly once.")


# dim_item has to stay one row per SKU, or it can't be used as a dimension
def check_gold_grain(con: duckdb.DuckDBPyConnection) -> None:
    total_rows, distinct_skus = con.execute(
        """
        SELECT COUNT(*), COUNT(DISTINCT "SKU")
        FROM gold.dim_item
        """
    ).fetchone()

    if total_rows != distinct_skus:
        raise RuntimeError(
            f"gold.dim_item has {total_rows} rows but only "
            f"{distinct_skus} distinct SKUs."
        )

    print(f"OK: gold.dim_item has {total_rows:,} rows, one per SKU.")


def build_item_master() -> None:
    print(f"\n{'=' * 60}")
    print("Starting: Silver + Gold Item Master")
    print(f"{'=' * 60}")

    con = None

    try:
        con = duckdb.connect(str(DB_PATH))

        run_sql_file(con, SILVER_ITEM_MASTER_SQL)
        report_silver(con)

        run_sql_file(con, GOLD_DIM_ITEM_SQL)
        check_gold_grain(con)

    finally:
        if con is not None:
            con.close()

    print("Completed: Silver + Gold Item Master")


def count_parquet_rows(parquet_path: Path) -> int:
    parquet_path_sql = str(parquet_path).replace("'", "''")

    con = duckdb.connect()

    try:
        return con.execute(
            f"""
            SELECT COUNT(*)
            FROM read_parquet('{parquet_path_sql}')
            """
        ).fetchone()[0]

    finally:
        con.close()


# copying dim_item.parquet to the other folders that read it
def copy_to_export_folders() -> None:
    if not ITEM_MASTER_EXPORT_FOLDERS:
        return

    print(f"\n{'=' * 60}")
    print("Starting: Copy Parquet to export folders")
    print(f"{'=' * 60}")

    source_path = PARQUET_FOLDER / "dim_item.parquet"
    expected_rows = count_parquet_rows(source_path)

    for folder in ITEM_MASTER_EXPORT_FOLDERS:
        folder_path = Path(folder)

        # a missing folder usually means the drive isn't mapped -- fail
        # instead of creating folders on the shared drive
        if not folder_path.is_dir():
            raise FileNotFoundError(
                f"Export folder not found: {folder_path}"
            )

        target_path = folder_path / source_path.name
        temp_path = folder_path / f"{source_path.name}.tmp"

        # copying under a temporary name and swapping it in, so anyone
        # reading the folder never picks up a half-written file
        shutil.copy2(source_path, temp_path)

        try:
            copied_rows = count_parquet_rows(temp_path)

            if copied_rows != expected_rows:
                raise RuntimeError(
                    f"Copy validation failed for {target_path}: "
                    f"expected {expected_rows} rows, "
                    f"the copy has {copied_rows}."
                )

            try:
                os.replace(temp_path, target_path)

            except PermissionError as error:
                raise RuntimeError(
                    f"Could not replace {target_path} -- "
                    f"is it open in Power BI or Excel? ({error})"
                ) from error

        finally:
            if temp_path.exists():
                temp_path.unlink()

        print(
            f"Parquet copied: {target_path} "
            f"({copied_rows} rows)"
        )

    print("Completed: Copy Parquet to export folders")


# main pipeline flow
def main() -> None:
    print("\nItem master ETL pipeline started.")

    try:
        run_python_step(
            "Extract item master from M3",
            EXTRACT_SCRIPT,
        )

        build_item_master()
        generate_parquet(GOLD_TABLES)
        copy_to_export_folders()

        print(f"\n{'=' * 60}")
        print(
            "Item master ETL pipeline "
            "completed successfully."
        )
        print(f"{'=' * 60}")

    except Exception as error:
        print(f"\n{'=' * 60}")
        print("Item master ETL pipeline failed.")
        print(f"Error: {error}")
        print(f"{'=' * 60}")

        sys.exit(1)


if __name__ == "__main__":
    main()
