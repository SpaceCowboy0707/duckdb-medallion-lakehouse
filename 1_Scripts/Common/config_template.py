#============================================================
# config.template.py — Configuration Template
#============================================================
# HOW TO USE:
#   1. Copy this file and rename the copy to:  config.py
#   2. Fill in your own source_path in Fetch_Tasks below.
#   3. config.py is gitignored — your local paths will NEVER
#      be pushed to GitHub.
#============================================================
 
#This file stores all configuration for the pipeline
#This file must live in 1_Scripts/Common/ — if moved,
#adjust the parents[2] index in ROOT_PATH below.
from pathlib import Path
 
#Find the root path of the project (auto-resolved, do not change)
ROOT_PATH = Path(__file__).resolve().parents[2]
 
#Lakehouse base directory — all data layer paths derive from this
LAKEHOUSE_PATH = ROOT_PATH / "2_Data_Lakehouse"
 
#Define the path for database
#lakehouse.db is gitignored — the pipeline creates it on the
#first run.
DB_PATH = LAKEHOUSE_PATH / "lakehouse.db"
 
#Define loading zone path
#Where all raw excel goes to before being processed
LOADING_ZONE_PATH = LAKEHOUSE_PATH / "0_Loading_Zone"
 
#Fetching files into the loading zone
#Each task: a name (for logging), a source folder, and
#a filename keyword — a file is fetched if its name contains it.
Fetch_Tasks = [
    {
        "task_name": "lead_time",
        "source_path": r"<YOUR_LOCAL_SOURCE_FOLDER_HERE>",
        "keywords": "Shipment Lead Time",
    },
    #Add more tasks following the same pattern:
    #{
    #    "task_name": "<TASK_NAME>",
    #    "source_path": r"<ANOTHER_LOCAL_FOLDER>",
    #    "keywords": "<FILENAME_KEYWORD>",
    #},
]

#M3 (SQL Server) connection for the item master extract
#SQL Server login. Use a read-only login where you can — either
#way the extract only ever sends a single SELECT and never commits.
#Fill these in config.py only — never in this template, which is
#pushed to GitHub.
M3_SERVER = r"<M3_SQL_SERVER_HOST>"
M3_DATABASE = r"<M3_DATABASE>"
M3_USERNAME = r"<M3_SQL_LOGIN>"
M3_PASSWORD = r"<M3_SQL_PASSWORD>"
M3_ODBC_DRIVER = "ODBC Driver 17 for SQL Server"

#M3 company number (CONO) the item master is pulled for
M3_COMPANY = "<M3_COMPANY_NUMBER>"

#Extra folders that get a copy of dim_item.parquet after each
#item master run (on top of 2_Data_Lakehouse/3_Gold). Leave the
#list empty to skip. Use the UNC form (\\server\share\...) if the
#pipeline is ever run from Task Scheduler.
ITEM_MASTER_EXPORT_FOLDERS = [
    #r"<ANOTHER_FOLDER_THAT_READS_DIM_ITEM>",
]