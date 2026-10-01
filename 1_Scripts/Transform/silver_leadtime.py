from __future__ import annotations
import re
from pathlib import Path
import duckdb

ROOT_PATH = Path(__file__).resolve().parents[2]
DB_PATH = ROOT_PATH / "2_Data_Lakehouse" / "lakehouse.db"

# the older files are not all in the same format, so we are adding them
# new tables will automatically get addeed
MANUAL_HISTORICAL_TABLES = [
    {
        "period": "2023",
        "table": "shipment_lead_time_2023_data",
        "where": "etd < DATE '2023-11-01'",
    },
    {
        "period": "2024_Q1",
        "table": "shipment_lead_time_2024_q1_data",
        "where": "etd >= DATE '2023-11-01' AND etd < DATE '2024-04-01'",
    },
    {
        "period": "2024_Q2",
        "table": "shipment_lead_time_2024_q2_data",
        "where": "etd >= DATE '2024-04-01' AND etd < DATE '2024-06-01'",
    },
    {
        "period": "2024_Q3",
        "table": "shipment_lead_time_2024_q3_data",
        "where": "etd >= DATE '2024-06-01' AND etd < DATE '2024-09-01'",
    },
    {
        "period": "2024_Q4",
        "table": "shipment_lead_time_2024_q4_data",
        "where": "etd >= DATE '2024-09-01' AND etd < DATE '2024-12-01'",
    },
    {
        "period": "2025_Q1",
        "table": "shipment_lead_time_2025_q1_data",
        "where": "etd >= DATE '2024-12-01' AND etd < DATE '2025-03-01'",
    },
    {
        "period": "2025_Q2",
        "table": "shipment_lead_time_2025_q2_data",
        "where": "etd >= DATE '2025-03-01' AND etd < DATE '2025-07-01'",
    },
]


# Tables deliberately kept out of Silver. Delete an entry to bring it back --
# nothing else needs changing.
#
# Use it for a workbook that matches the naming pattern and passes the column
# check but isn't a detail table -- e.g. a placeholder export that shares a few
# column names, whose dates don't parse and whose duration fields hold dates
# (that breaks the union with a BIGINT -> TIMESTAMP cast).
#   e.g. SKIPPED_DETAIL_TABLES = {"shipment_lead_time_2026_q2_export"}
SKIPPED_DETAIL_TABLES: set[str] = set()

# starting dynamic tables from 2025 Q3
DYNAMIC_START_PERIOD = (2025, 3)

# this is the final column order we would want in the Silver table
FINAL_COLUMNS = [
    "wh",
    "asn",
    "folio",
    "div",
    "container_size",
    "vessel",
    "b_l",
    "port",
    "container",
    "min_req_delivery_date",
    "max_req_delivery_date",
    "xfty_range",
    "xfty_to_container_consolidation",
    "pos_consolidation_to_gate_in",
    "gate_in",
    "gate_in_to_etd",
    "etd",
    "etd_to_eta",
    "current_eta_port",
    "eta_to_delivery",
    "p_u",
    "delivery_to_received",
    "asn_receive",
    "max_xft_to_received",
    "min_xft_to_received",
    "avg_xfty_to_received",
    "customer",
    "region",
    "asn_qty",
    "_source_period",
    "_bronze_insert_ts",
    "_source_file_name",
]


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


# getting all lead time tables from the bronze layer
def get_bronze_tables(con: duckdb.DuckDBPyConnection) -> list[str]:
    rows = con.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'bronze'
          AND table_name ILIKE '%lead_time%'
        ORDER BY table_name
    """).fetchall()

    return [row[0] for row in rows]


# checkking which columns are available in this table
def get_columns(con: duckdb.DuckDBPyConnection, table_name: str) -> set[str]:
    rows = con.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'bronze'
          AND table_name = ?
    """, [table_name]).fetchall()

    return {row[0].lower() for row in rows}


def table_exists(con: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    result = con.execute("""
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = 'bronze'
          AND table_name = ?
    """, [table_name]).fetchone()[0]

    return result > 0


# pulling the year and quarter from the table names
def parse_period(table_name: str) -> tuple[str, int, int] | None:
    match = re.search(r"shipment_lead_time_(\d{4})_q([1-4])", table_name)
    if not match:
        return None

    year = int(match.group(1))
    quarter = int(match.group(2))
    period = f"{year}_Q{quarter}"

    return period, year, quarter


# to ignore summary tables and other tables that we don't want in the silver layer
def is_non_detail_table(table_name: str) -> bool:
    lowered = table_name.lower()

    # the per-warehouse summary tabs are named after the warehouse -- add
    # their suffixes here (e.g. "_wh_east")
    excluded_endings = (
        "_summary",
        "_port_table",
        "_whr_code",
        "_2024_air",
        "_2024_ocean",
    )

    return (
        lowered in SKIPPED_DETAIL_TABLES
        or lowered.startswith("copy_of_")
        or "old_version_do_not_use" in lowered
        or lowered.endswith(excluded_endings)
    )


# some files use different column names, so to use whichever one exists
def pick_column(columns: set[str], candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


# dates in different formats
def date_value_expr(source_column: str) -> str:
    col = quote_identifier(source_column)
    return f"""COALESCE(
        TRY_CAST({col} AS DATE),
        TRY_STRPTIME(TRIM(CAST({col} AS VARCHAR)), '%Y-%m-%d %H:%M:%S')::DATE,
        TRY_STRPTIME(TRIM(CAST({col} AS VARCHAR)), '%Y-%m-%d')::DATE,
        TRY_STRPTIME(TRIM(CAST({col} AS VARCHAR)), '%m/%d/%y')::DATE,
        TRY_STRPTIME(TRIM(CAST({col} AS VARCHAR)), '%m/%d/%Y')::DATE,
        TRY_STRPTIME(TRIM(CAST({col} AS VARCHAR)), '%m-%d-%Y')::DATE
    )"""


def date_expr(source_column: str, alias: str) -> str:
    return f"{date_value_expr(source_column)} AS {quote_identifier(alias)}"


def standard_expr(
    columns: set[str],
    alias: str,
    candidates: list[str],
    *,
    is_date: bool = False,
    required: bool = True,
) -> str:
    source = pick_column(columns, candidates)

    if source is None:
        if required:
            raise ValueError(f"Required column for {alias} not found. Tried {candidates}")
        return f"NULL AS {quote_identifier(alias)}"

    if is_date:
        return date_expr(source, alias)

    return f"{quote_identifier(source)} AS {quote_identifier(alias)}"


# the leg durations are carried over from the spreadsheet, not recalculated --
# the 2023 layout puts dates in columns that do not match its own formulas, so
# recomputing them here would corrupt more rows than it fixes. but a value is
# only meaningful when both dates it spans actually parsed: a blank cell reads
# as Excel's zero date (1899-12-30) and the sheet returns a ~45,900 day gap
# instead of leaving it empty. keep the source number, drop the impossible ones.
def guarded_interval_expr(
    columns: set[str],
    alias: str,
    candidates: list[str],
    start_candidates: list[str],
    end_candidates: list[str],
) -> str:
    source = pick_column(columns, candidates)

    if source is None:
        raise ValueError(f"Required column for {alias} not found. Tried {candidates}")

    start = pick_column(columns, start_candidates)
    end = pick_column(columns, end_candidates)

    if start is None or end is None:
        return f"{quote_identifier(source)} AS {quote_identifier(alias)}"

    return f"""CASE
        WHEN {date_value_expr(start)} IS NULL
          OR {date_value_expr(end)} IS NULL
        THEN NULL
        ELSE {quote_identifier(source)}
    END AS {quote_identifier(alias)}"""


def build_select_sql(
    table_name: str,
    period: str,
    columns: set[str],
    where_clause: str | None,
) -> str:
    # the 2023 / 2024-Q1 template labels the two xft columns the wrong way round:
    # what it calls the minimum is the maximum and vice versa. the range column
    # is the version marker -- the business renamed it min_max_xfty ->
    # max_min_xfty in the same republish that fixed the labels, so key off that
    # rather than a hardcoded period list and any older file still lands right.
    legacy_xft_layout = "min_max_xfty" in columns

    expressions = [
        standard_expr(columns, "wh", ["wh", "whr"]),
        standard_expr(columns, "asn", ["asn"]),
        standard_expr(columns, "folio", ["folio"]),
        standard_expr(columns, "div", ["div"], required=False),
        standard_expr(columns, "container_size", ["continer_size", "container_size"], required=False),
        standard_expr(columns, "vessel", ["vessel"], required=False),
        standard_expr(columns, "b_l", ["b_l"]),
        standard_expr(columns, "port", ["port"]),
        standard_expr(columns, "container", ["container"]),
        standard_expr(
            columns,
            "min_req_delivery_date",
            ["min_of_po_head_req_delivery_date", "min_header_delivery_date"],
            is_date=True,
        ),
        standard_expr(
            columns,
            "max_req_delivery_date",
            ["max_of_po_head_req_delivery_date", "max_header_delivery_date"],
            is_date=True,
        ),
        standard_expr(columns, "xfty_range", ["min_max_xfty", "max_min_xfty"]),
        standard_expr(columns, "xfty_to_container_consolidation", ["xfty_to_container_consolidation"]),
        standard_expr(columns, "pos_consolidation_to_gate_in", ["pos_consolidation_to_gate_in"]),
        standard_expr(columns, "gate_in", ["gate_in"], is_date=True),
        guarded_interval_expr(columns, "gate_in_to_etd", ["gate_in_to_etd"], ["gate_in"], ["etd"]),
        standard_expr(columns, "etd", ["etd"], is_date=True),
        guarded_interval_expr(columns, "etd_to_eta", ["etd_to_eta"], ["etd"], ["current_eta_port", "eta"]),
        standard_expr(columns, "current_eta_port", ["current_eta_port", "eta"], is_date=True),
        guarded_interval_expr(columns, "eta_to_delivery", ["eta_to_delivery"], ["current_eta_port", "eta"], ["p_u"]),
        standard_expr(columns, "p_u", ["p_u"], is_date=True),
        guarded_interval_expr(columns, "delivery_to_received", ["delivery_to_received"], ["p_u"], ["asn_receive"]),
        standard_expr(columns, "asn_receive", ["asn_receive"], is_date=True),
        standard_expr(
            columns,
            "max_xft_to_received",
            ["min_xft_to_received"] if legacy_xft_layout else ["max_xft_to_received"],
        ),
        standard_expr(
            columns,
            "min_xft_to_received",
            ["max_xft_to_received"] if legacy_xft_layout else ["min_xft_to_received"],
        ),
        standard_expr(columns, "avg_xfty_to_received", ["avg_xfty_to_received"]),
        standard_expr(columns, "customer", ["customer"], required=False),
        standard_expr(columns, "region", ["region"]),
        standard_expr(columns, "asn_qty", ["asn_qty"], required=False),
        f"'{period}' AS _source_period",
        standard_expr(columns, "_bronze_insert_ts", ["_bronze_insert_ts"]),
        standard_expr(columns, "_source_file_name", ["_source_file_name"]),
    ]

    select_sql = f"""
SELECT
    {",\n    ".join(expressions)}
FROM bronze.{quote_identifier(table_name)}
"""

    if where_clause:
        select_sql += f"WHERE {where_clause}\n"

    return select_sql


# checking the table has everything
def is_valid_dynamic_detail_table(columns: set[str]) -> bool:
    required_groups = [
        ["wh", "whr"],
        ["asn"],
        ["folio"],
        ["b_l"],
        ["port"],
        ["region"],
        ["container"],
        ["min_of_po_head_req_delivery_date", "min_header_delivery_date"],
        ["max_of_po_head_req_delivery_date", "max_header_delivery_date"],
        ["min_max_xfty", "max_min_xfty"],
        ["xfty_to_container_consolidation"],
        ["pos_consolidation_to_gate_in"],
        ["gate_in"],
        ["gate_in_to_etd"],
        ["etd"],
        ["etd_to_eta"],
        ["current_eta_port", "eta"],
        ["eta_to_delivery"],
        ["p_u"],
        ["delivery_to_received"],
        ["asn_receive"],
        ["max_xft_to_received"],
        ["min_xft_to_received"],
        ["avg_xfty_to_received"],
        ["_bronze_insert_ts"],
        ["_source_file_name"],
    ]

    return all(pick_column(columns, group) is not None for group in required_groups)


# to look for newer quarter tables automatically
def discover_dynamic_tables(con: duckdb.DuckDBPyConnection) -> list[dict[str, str | None]]:
    dynamic_tables = []

    for table_name in get_bronze_tables(con):
        parsed = parse_period(table_name)
        if not parsed:
            continue

        period, year, quarter = parsed

        if (year, quarter) < DYNAMIC_START_PERIOD:
            continue

        if is_non_detail_table(table_name):
            continue

        columns = get_columns(con, table_name)

        if not is_valid_dynamic_detail_table(columns):
            continue

        dynamic_tables.append({
            "period": period,
            "table": table_name,
            "where": None,
        })

    dynamic_tables.sort(key=lambda item: parse_period(str(item["table"]))[1:])

    return dynamic_tables


# the main flow
def main() -> None:
    con = duckdb.connect(str(DB_PATH))

    included_tables = []
    select_blocks = []

    # starting with the older tables that need manual mapping
    for item in MANUAL_HISTORICAL_TABLES:
        table_name = str(item["table"])

        if not table_exists(con, table_name):
            print(f"Skipped missing manual table: {table_name}")
            continue

        columns = get_columns(con, table_name)
        select_blocks.append(
            build_select_sql(
                table_name=table_name,
                period=str(item["period"]),
                columns=columns,
                where_clause=str(item["where"]),
            )
        )
        included_tables.append(item)

    # picking up any newer tables that match the expected format
    dynamic_tables = discover_dynamic_tables(con)

    for item in dynamic_tables:
        table_name = str(item["table"])
        columns = get_columns(con, table_name)

        select_blocks.append(
            build_select_sql(
                table_name=table_name,
                period=str(item["period"]),
                columns=columns,
                where_clause=None,
            )
        )
        included_tables.append(item)

    if not select_blocks:
        raise RuntimeError("No valid Bronze leadtime detail tables were found.")

    # combining all together
    union_sql = "\nUNION ALL\n".join(select_blocks)

    # final silver table
    final_sql = f"""
CREATE OR REPLACE TABLE silver.leadtime_data AS

WITH unified_leadtime AS (
{union_sql}
),

deduped_leadtime AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY wh, asn, folio, b_l, container, etd
            ORDER BY _bronze_insert_ts DESC, _source_file_name
        ) AS row_num
    FROM unified_leadtime
),

normalized AS (
    SELECT
        NULLIF(TRIM(UPPER(CAST(wh AS VARCHAR))), '') AS wh,
        NULLIF(TRIM(CAST(asn AS VARCHAR)), '') AS asn,
        NULLIF(TRIM(CAST(folio AS VARCHAR)), '') AS folio,
        NULLIF(TRIM(UPPER(CAST(div AS VARCHAR))), '') AS div,
        NULLIF(TRIM(UPPER(CAST(container_size AS VARCHAR))), '') AS container_size,
        vessel,
        b_l,
        NULLIF(LOWER(TRIM(REGEXP_REPLACE(CAST(port AS VARCHAR), '\\s+', ' ', 'g'))), '') AS normalized_port,
        container,
        min_req_delivery_date,
        max_req_delivery_date,
        xfty_range,
        xfty_to_container_consolidation,
        pos_consolidation_to_gate_in,
        gate_in,
        gate_in_to_etd,
        etd,
        etd_to_eta,
        current_eta_port,
        eta_to_delivery,
        p_u,
        delivery_to_received,
        asn_receive,
        max_xft_to_received,
        min_xft_to_received,
        avg_xfty_to_received,
        NULLIF(TRIM(UPPER(CAST(customer AS VARCHAR))), '') AS customer,
        NULLIF(TRIM(UPPER(CAST(region AS VARCHAR))), '') AS region,
        asn_qty,
        _source_period,
        _bronze_insert_ts,
        _source_file_name
    FROM deduped_leadtime
    WHERE row_num = 1
),

cleaned AS (
    SELECT
        wh,
        asn,
        folio,
        div,
        container_size,
        vessel,
        b_l,
        UPPER(
            CASE
                WHEN normalized_port = 'xiangang' THEN 'xingang'
                WHEN normalized_port = 'sekou' THEN 'shekou'
                WHEN normalized_port = 'hochiminh' THEN 'ho chi minh'
                WHEN normalized_port = 'nhava sheva, in' THEN 'nhava sheva'
                WHEN normalized_port = 'phnom penh, kh' THEN 'phnom penh'
                WHEN normalized_port = 'chattogram' THEN 'chittagong'
                WHEN normalized_port = 'haiphong, vn' THEN 'haiphong'
                WHEN normalized_port = 'santos, brazil' THEN 'santos'
                WHEN normalized_port = 'sines portugal' THEN 'sines'
                WHEN normalized_port = 'vung tau, vn' THEN 'vung tau'
                ELSE normalized_port
            END
        ) AS port,
        container,
        min_req_delivery_date,
        max_req_delivery_date,
        xfty_range,
        xfty_to_container_consolidation,
        pos_consolidation_to_gate_in,
        gate_in,
        gate_in_to_etd,
        etd,
        etd_to_eta,
        current_eta_port,
        eta_to_delivery,
        p_u,
        delivery_to_received,
        asn_receive,
        max_xft_to_received,
        min_xft_to_received,
        avg_xfty_to_received,
        customer,
        region,
        asn_qty,
        _source_period,
        _bronze_insert_ts,
        _source_file_name
    FROM normalized
)

SELECT
    {",\n    ".join(FINAL_COLUMNS)}
FROM cleaned
ORDER BY etd;
"""

    con.execute(final_sql)

    # a small check for the presence of all bronze tables
    print("\nIncluded Bronze detail tables:")
    for item in included_tables:
        print(f"- {item['period']}: {item['table']}")

    print("\nSilver row counts by source period:")
    row_counts = con.execute("""
        SELECT
            _source_period,
            COUNT(*) AS row_count,
            MIN(etd) AS min_etd,
            MAX(etd) AS max_etd
        FROM silver.leadtime_data
        GROUP BY _source_period
        ORDER BY _source_period
    """).fetchdf()
    print(row_counts)

    print("\nFinal Silver summary:")
    summary = con.execute("""
        SELECT
            COUNT(*) AS total_rows,
            MIN(etd) AS min_etd,
            MAX(etd) AS max_etd,
            COUNT(DISTINCT _source_period) AS source_periods
        FROM silver.leadtime_data
    """).fetchdf()
    print(summary)

    print("\nDuplicate shipment key check:")
    duplicates = con.execute("""
        SELECT
            wh,
            asn,
            folio,
            b_l,
            container,
            etd,
            COUNT(*) AS duplicate_count
        FROM silver.leadtime_data
        GROUP BY wh, asn, folio, b_l, container, etd
        HAVING COUNT(*) > 1
        ORDER BY duplicate_count DESC
        LIMIT 20
    """).fetchdf()
    print(duplicates)

    print(
        "\nNull ETD check "
        "(rows with NULL etd may have been silently lost during dedup):"
    )

    null_etd = con.execute("""
        SELECT COUNT(*) AS null_etd_rows
        FROM silver.leadtime_data
        WHERE etd IS NULL
    """).fetchone()[0]

    if null_etd > 0:
        print(
            f"WARNING: {null_etd} row(s) have NULL etd — "
            "dedup may have collapsed distinct shipments."
        )
    else:
        print("OK: no NULL etd rows.")

    print("\nNull check for key fields:")
    nulls = con.execute("""
        SELECT
            _source_period,
            COUNT(*) AS total_rows,
            SUM(CASE WHEN wh IS NULL THEN 1 ELSE 0 END) AS null_wh,
            SUM(CASE WHEN asn IS NULL THEN 1 ELSE 0 END) AS null_asn,
            SUM(CASE WHEN etd IS NULL THEN 1 ELSE 0 END) AS null_etd,
            SUM(CASE WHEN current_eta_port IS NULL THEN 1 ELSE 0 END) AS null_eta,
            SUM(CASE WHEN p_u IS NULL THEN 1 ELSE 0 END) AS null_p_u,
            SUM(CASE WHEN asn_receive IS NULL THEN 1 ELSE 0 END) AS null_asn_receive
        FROM silver.leadtime_data
        GROUP BY _source_period
        ORDER BY _source_period
    """).fetchdf()
    print(nulls)

    con.close()


if __name__ == "__main__":
    main()