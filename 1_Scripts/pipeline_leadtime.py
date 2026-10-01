from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import duckdb


# project paths
ROOT_PATH = Path(__file__).resolve().parents[1]

FETCH_SCRIPT = (
    ROOT_PATH
    / "1_Scripts"
    / "Extract"
    / "fetch_source_files.py"
)

BRONZE_SCRIPT = (
    ROOT_PATH
    / "1_Scripts"
    / "Extract"
    / "load_to_bronze.py"
)

SILVER_SCRIPT = (
    ROOT_PATH
    / "1_Scripts"
    / "Transform"
    / "silver_leadtime.py"
)

GOLD_DIM_DATE_SQL = (
    ROOT_PATH
    / "1_Scripts"
    / "Transform"
    / "Queries"
    / "gold_dim_date.sql"
)

GOLD_LEADTIME_SQL = (
    ROOT_PATH
    / "1_Scripts"
    / "Transform"
    / "Queries"
    / "gold_leadtime.sql"
)

DB_PATH = (
    ROOT_PATH
    / "2_Data_Lakehouse"
    / "lakehouse.db"
)

PARQUET_FOLDER = (
    ROOT_PATH
    / "2_Data_Lakehouse"
    / "3_Gold"
)

GOLD_TABLES = [
    "dim_country",
    "dim_date",
    "dim_phase",
    "dim_port",
    "dim_wh",
    "fact_leadtime",
]


# run every python step one by one
def run_python_step(step_name: str, script_path: Path) -> None:
    print(f"\n{'=' * 60}")
    print(f"Starting: {step_name}")
    print(f"{'=' * 60}")

    if not script_path.exists():
        raise FileNotFoundError(
            f"Script not found: {script_path}"
        )

    process = subprocess.Popen(
        [sys.executable, str(script_path)],
        cwd=ROOT_PATH,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    warning_lines = []

    if process.stdout is None:
        raise RuntimeError(
            f"Could not read output from {step_name}."
        )

    for line in process.stdout:
        print(line, end="")

        if "WARNING:" in line:
            warning_lines.append(line.strip())

    return_code = process.wait()

    if return_code != 0:
        raise RuntimeError(
            f"{step_name} failed with exit code "
            f"{return_code}."
        )

    if warning_lines:
        warnings = "\n".join(warning_lines)

        raise RuntimeError(
            f"{step_name} reported an error:\n"
            f"{warnings}"
        )

    print(f"Completed: {step_name}")


# run the existing gold sql files
def run_gold_sql() -> None:
    print(f"\n{'=' * 60}")
    print("Starting: Gold Leadtime")
    print(f"{'=' * 60}")

    con = None

    try:
        con = duckdb.connect(str(DB_PATH))

        for sql_file in [
            GOLD_DIM_DATE_SQL,
            GOLD_LEADTIME_SQL,
        ]:
            if not sql_file.exists():
                raise FileNotFoundError(
                    f"Gold SQL file not found: {sql_file}"
                )

            print(f"Running: {sql_file.name}")

            sql = sql_file.read_text(
                encoding="utf-8"
            )

            con.execute(sql)

            print(f"Completed: {sql_file.name}")

    finally:
        if con is not None:
            con.close()

    print("Completed: Gold Leadtime")


# export all gold tables to parquet
def generate_parquet(table_names: list[str] = GOLD_TABLES) -> None:
    print(f"\n{'=' * 60}")
    print("Starting: Generate Parquet")
    print(f"{'=' * 60}")

    PARQUET_FOLDER.mkdir(
        parents=True,
        exist_ok=True,
    )

    con = None

    try:
        con = duckdb.connect(str(DB_PATH))

        for table_name in table_names:
            parquet_path = (
                PARQUET_FOLDER
                / f"{table_name}.parquet"
            )

            if parquet_path.exists():
                parquet_path.unlink()

            parquet_path_sql = str(
                parquet_path
            ).replace("'", "''")

            con.execute(
                f"""
                COPY (
                    SELECT *
                    FROM gold.{table_name}
                )
                TO '{parquet_path_sql}'
                (FORMAT PARQUET)
                """
            )

            # checking the parquet rows before finishing
            gold_rows = con.execute(
                f"""
                SELECT COUNT(*)
                FROM gold.{table_name}
                """
            ).fetchone()[0]

            parquet_rows = con.execute(
                f"""
                SELECT COUNT(*)
                FROM read_parquet('{parquet_path_sql}')
                """
            ).fetchone()[0]

            if gold_rows != parquet_rows:
                raise RuntimeError(
                    f"Parquet validation failed for {table_name}: "
                    f"Gold contains {gold_rows} rows but "
                    f"Parquet contains {parquet_rows} rows."
                )

            print(
                f"Parquet saved: {table_name}.parquet "
                f"({parquet_rows} rows)"
            )

    finally:
        if con is not None:
            con.close()

    print("Completed: Generate Parquet")


# main pipeline flow
def main() -> None:
    print("\nLeadtime ETL pipeline started.")

    try:
        run_python_step(
            "Extract files",
            FETCH_SCRIPT,
        )

        run_python_step(
            "Load files to Bronze",
            BRONZE_SCRIPT,
        )

        run_python_step(
            "Silver Leadtime",
            SILVER_SCRIPT,
        )

        run_gold_sql()
        generate_parquet()

        print(f"\n{'=' * 60}")
        print(
            "Leadtime ETL pipeline "
            "completed successfully."
        )
        print(f"{'=' * 60}")

    except Exception as error:
        print(f"\n{'=' * 60}")
        print("Leadtime ETL pipeline failed.")
        print(f"Error: {error}")
        print(f"{'=' * 60}")

        sys.exit(1)


if __name__ == "__main__":
    main()