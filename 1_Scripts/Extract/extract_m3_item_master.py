import re
import sys
from pathlib import Path

import duckdb
import pandas as pd
import pyodbc

sys.path.append(str(Path(__file__).resolve().parents[1] / "Common"))
from config import (
    DB_PATH,
    M3_COMPANY,
    M3_DATABASE,
    M3_ODBC_DRIVER,
    M3_PASSWORD,
    M3_SERVER,
    M3_USERNAME,
)


QUERY_PATH = Path(__file__).resolve().parent / "Queries" / "m3_item_master.sql"

# the M3 login may be able to write, so anything that isn't a plain SELECT is
# refused before it is ever sent to the server
FORBIDDEN_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "MERGE", "TRUNCATE", "INTO",
    "CREATE", "ALTER", "DROP", "RENAME",
    "EXEC", "EXECUTE", "GRANT", "REVOKE", "DENY",
    "USE", "DECLARE", "SET", "BEGIN", "COMMIT", "ROLLBACK", "SAVE",
    "BULK", "OPENROWSET", "OPENQUERY", "OPENDATASOURCE",
    "BACKUP", "RESTORE", "DBCC", "KILL", "SHUTDOWN", "RECONFIGURE",
]

# quoted text, [bracketed] names and comments -- matched in one pass so a
# "--" inside a string can't hide the rest of the line, and an alias like
# 'Unit of Measure' can't be mistaken for a keyword
LITERALS_AND_COMMENTS = re.compile(
    r"'(?:[^']|'')*'"
    r'|"(?:[^"]|"")*"'
    r"|\[[^\]]*\]"
    r"|--[^\n]*"
    r"|/\*.*?\*/",
    re.DOTALL,
)


# making sure the query can only read
def assert_read_only(sql):
    code_only = LITERALS_AND_COMMENTS.sub(" ", sql).strip()

    if not re.match(r"(SELECT|WITH)\b", code_only, re.IGNORECASE):
        raise ValueError("M3 query must start with SELECT or WITH.")

    if ";" in code_only.rstrip(";"):
        raise ValueError("M3 query must be a single statement.")

    pattern = r"\b(" + "|".join(FORBIDDEN_KEYWORDS) + r")\b"
    found = sorted({word.upper() for word in re.findall(pattern, code_only, re.IGNORECASE)})

    if found:
        raise ValueError(
            f"M3 query contains keywords that are not allowed: {', '.join(found)}"
        )


# ODBC values with ; or } in them have to be wrapped in braces
def odbc_value(value):
    return "{" + str(value).replace("}", "}}") + "}"


def build_connection_string():
    settings = (M3_SERVER, M3_DATABASE, M3_USERNAME, M3_PASSWORD, M3_COMPANY)

    if any(str(value).startswith("<") for value in settings):
        raise ValueError(
            "M3_SERVER / M3_DATABASE / M3_USERNAME / M3_PASSWORD / M3_COMPANY "
            "are still placeholders in 1_Scripts/Common/config.py."
        )

    return (
        f"DRIVER={odbc_value(M3_ODBC_DRIVER)};"
        f"SERVER={odbc_value(M3_SERVER)};"
        f"DATABASE={odbc_value(M3_DATABASE)};"
        f"UID={odbc_value(M3_USERNAME)};"
        f"PWD={odbc_value(M3_PASSWORD)};"
        "ApplicationIntent=ReadOnly;"
    )


# reading everything from M3 before touching the lakehouse, so a failed or
# half-finished read never replaces a good bronze table
def fetch_from_m3(sql):
    con = pyodbc.connect(build_connection_string(), autocommit=False, timeout=30)

    try:
        con.timeout = 600
        cursor = con.cursor()
        # the company number is bound to the query's single ? marker
        cursor.execute(sql, int(M3_COMPANY))

        columns = [column[0] for column in cursor.description]
        rows = [tuple(row) for row in cursor.fetchall()]

    finally:
        # nothing is ever committed; rolling back closes the read transaction
        con.rollback()
        con.close()

    return pd.DataFrame.from_records(rows, columns=columns)


def load_to_bronze(df):
    # same column cleaning as the excel loader
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(r"[^a-z0-9]+", "_", regex=True)
        .str.strip("_")
    )

    # landing everything as text, exactly as M3 sent it (padding included);
    # silver trims and sets the types
    df_bronze = df.astype("string")

    con = duckdb.connect(str(DB_PATH))

    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
        con.execute(f"""
            CREATE OR REPLACE TABLE bronze.m3_item_master AS
            SELECT
                *,
                CURRENT_TIMESTAMP AS _bronze_insert_ts,
                '{QUERY_PATH.name}' AS _source_file_name
            FROM df_bronze
        """)

    finally:
        con.close()


def main():
    sql = QUERY_PATH.read_text(encoding="utf-8")
    assert_read_only(sql)

    print(f"Reading item master from M3 ({M3_SERVER} / {M3_DATABASE})...")
    df = fetch_from_m3(sql)

    if df.empty:
        raise RuntimeError(
            "M3 returned 0 rows -- keeping the existing bronze.m3_item_master."
        )

    print(f"  -> {len(df):,} rows, {len(df.columns)} columns")

    load_to_bronze(df)
    print("Loaded into table: bronze.m3_item_master")


if __name__ == "__main__":
    main()
