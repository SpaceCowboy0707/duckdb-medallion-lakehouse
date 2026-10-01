import pandas as pd
import duckdb
import sys
import re
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "Common"))
from config import DB_PATH, LOADING_ZONE_PATH


# cleaning the file name properly
def clean_file_name(filename):
    clean_name = filename.lower()
    clean_name = re.sub(r"[^\w]+", "_", clean_name)
    return clean_name.strip("_")


# loading all excel files into the bronze layer
def load_files_to_bronze():
    print(f"Connecting to DuckDB at: {DB_PATH}")
    con = duckdb.connect(str(DB_PATH))

    # make sure bronze layer is created
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze")

    # getting all excel files from the loading zone
    excel_files = list(LOADING_ZONE_PATH.glob("*.xlsx"))

    if not excel_files:
        print(
            f"No excel files found in the loading zone. "
            f"Please check {LOADING_ZONE_PATH} and run the fetch script first."
        )
        return

    for file in excel_files:
        table_name = clean_file_name(file.stem)

        try:
            print(f"Loading {file.name}...")

            # reading all tabs from the excel file
            all_sheets = pd.read_excel(file, sheet_name=None)

            # going through each tab and loading it separately
            for sheet_name, df_bronze in all_sheets.items():

                # cleaning column names
                df_bronze.columns = (
                    df_bronze.columns
                    .str.strip()
                    .str.lower()
                    .str.replace(r"[^a-z0-9]+", "_", regex=True)
                    .str.strip("_")
                )

                # removing rows that are completely blank
                df_bronze = df_bronze.dropna(how="all")

                # removing the q3 row that only has region filled
                if (
                    file.name == "Shipment Lead Time 2025 Q3.xlsx"
                    and clean_file_name(sheet_name) == "q3_2025"
                    and "region" in df_bronze.columns
                ):
                    other_columns = [
                        column for column in df_bronze.columns
                        if column != "region"
                    ]

                    df_bronze = df_bronze[
                        ~(
                            (df_bronze["region"] == "VIETNAM")
                            & df_bronze[other_columns].isna().all(axis=1)
                        )
                    ]

                # keeping asn and folio as text since some values have letters as well
                for column in ["asn", "folio"]:
                    if column in df_bronze.columns:
                        df_bronze[column] = df_bronze[column].astype("string")

                # keeping p_u as text when the source has mixed date and time values
                if "p_u" in df_bronze.columns:
                    df_bronze["p_u"] = df_bronze["p_u"].astype("string")

                clean_sheet = clean_file_name(sheet_name)
                final_table_name = f"{table_name}_{clean_sheet}"

                # loading sheet into bronze layer
                con.execute(f"""
                    CREATE OR REPLACE TABLE bronze.{final_table_name} AS
                    SELECT
                        *,
                        CURRENT_TIMESTAMP AS _bronze_insert_ts,
                        '{file.name}' AS _source_file_name
                    FROM df_bronze
                """)

                print(
                    f"  -> Successfully loaded tab '{sheet_name}' "
                    f"into table: bronze.{final_table_name}"
                )

            print("")

        except Exception as e:
            print(
                f"❌ WARNING: Failed to load {file.name} "
                f"into bronze layer: {e}\n"
            )

    con.close()
    print("Finished loading all files and tabs into the bronze layer.")


if __name__ == "__main__":
    load_files_to_bronze()