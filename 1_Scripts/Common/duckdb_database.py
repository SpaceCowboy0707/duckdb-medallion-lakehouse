#Get the path for database
import duckdb
from config import DB_PATH

#Setup connection
def get_connection():
        #Connect to the database
        con = duckdb.connect(str(DB_PATH))

        #Create Medallion Structure
        con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
        con.execute("CREATE SCHEMA IF NOT EXISTS silver")
        con.execute("CREATE SCHEMA IF NOT EXISTS gold")

        return con


if __name__ == "__main__":
    # SAVE BLOCK
    con = get_connection()
    print("Database initialized successfully at:", DB_PATH)


    print(con.sql("SELECT * FROM information_schema.schemata"))