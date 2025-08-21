import json
import re
import streamlit as st
from langchain_community.utilities import SQLDatabase



def get_schema():
    return db.get_table_info()

def get_cleaned_create_statements(connection_uri: str) -> str:
    """
    Connects to the database using the given SQLAlchemy connection URL, retrieves the 
    table information via SQLDatabase.get_table_info(), and returns only the CREATE TABLE 
    statements (each ending with a semicolon), without the example rows.

    Args:
        connection_uri (str): The SQLAlchemy connection URL for the target database.

    Returns:
        str: A string containing the cleaned CREATE TABLE statements, separated by two newlines.
    
    Expected output format:
    
    CREATE TABLE albums ( "AlbumId" INTEGER NOT NULL, "Title" NVARCHAR(160) NOT NULL, "ArtistId" INTEGER NOT NULL, PRIMARY KEY ("AlbumId"), FOREIGN KEY("ArtistId") REFERENCES artists ("ArtistId") );
    
    CREATE TABLE artists ( "ArtistId" INTEGER NOT NULL, "Name" NVARCHAR(120), PRIMARY KEY ("ArtistId") );
    """
    # Instantiate the SQLDatabase object from the provided URI.
    db = SQLDatabase.from_uri(connection_uri)
    # Retrieve the raw table information (which may include comment blocks with example rows).
    raw_info = db.get_table_info()
    
    # Remove any comment blocks (e.g., /* ... */) from the output.
    cleaned_info = re.sub(r'/\*.*?\*/', '', raw_info, flags=re.DOTALL).strip()
    
    # Split the cleaned output into individual statements.
    # This assumes that each CREATE TABLE statement is separated by one or more blank lines.
    statements = [stmt.strip() for stmt in cleaned_info.split("\n\n") if stmt.strip()]
    
    # Ensure each statement ends with a semicolon.
    statements = [stmt if stmt.endswith(";") else stmt + ";" for stmt in statements]
    
    # Join the statements back together with two newlines between each.
    final_output = "\n\n".join(statements)
    
    return final_output

def clean_create_table_statements(sql: str) -> str:
    """
    Extracts and cleans all CREATE TABLE statements from the input SQL schema.
    The cleaning steps include:
    - Removing MySQL-specific options (ENGINE, CHARSET, COLLATE).
    - Removing unnecessary backticks.
    - Extracting each CREATE TABLE statement by balancing parentheses.
    - Formatting with proper indentation.
    - Ensuring each statement ends with a semicolon.
    
    Args:
        sql (str): Raw SQL containing one or more CREATE TABLE statements, possibly with extra text.
    
    Returns:
        str: Cleaned and formatted CREATE TABLE statements as a schema.
    """
    cleaned_statements = []
    lower_sql = sql.lower()
    pos = 0

    while True:
        start = lower_sql.find("create table", pos)
        if start == -1:
            break

        # Find the first opening parenthesis after "create table"
        first_paren = lower_sql.find("(", start)
        if first_paren == -1:
            break

        count = 0
        end = None
        in_quote = False
        quote_char = ""
        for i in range(first_paren, len(sql)):
            ch = sql[i]
            if ch in ("'", '"'):
                if not in_quote:
                    in_quote = True
                    quote_char = ch
                elif ch == quote_char:
                    in_quote = False
            if in_quote:
                continue
            if ch == "(":
                count += 1
            elif ch == ")":
                count -= 1
                if count == 0:
                    end = i
                    break

        if end is None:
            # If no matching closing is found, exit the loop.
            break

        # Extract the CREATE TABLE statement (from start to the matching ')')
        stmt = sql[start:end + 1]

        # Remove MySQL-specific options (ENGINE, CHARSET, COLLATE)
        stmt = re.sub(
            r"\s*ENGINE=\w+(?:\s+DEFAULT\s+CHARSET=\w+(?:\s+COLLATE=\w+)?)?;?",
            "",
            stmt,
            flags=re.IGNORECASE
        )
        # Remove backticks around identifiers
        stmt = stmt.replace("`", "")

        # Format the statement:
        # Insert a newline and 4 spaces after the first opening parenthesis.
        stmt = re.sub(r"\(\s*", "(\n    ", stmt, count=1)
        # Insert a newline and 4 spaces after each comma.
        stmt = re.sub(r",\s*", ",\n    ", stmt)
        # Ensure the closing parenthesis is on a new line.
        stmt = re.sub(r"\s*\)\s*$", "\n)", stmt)

        stmt = stmt.strip()
        # Ensure the statement ends with a semicolon.
        if not stmt.endswith(";"):
            stmt += ";"

        cleaned_statements.append(stmt)
        pos = end + 1

    return "\n\n".join(cleaned_statements)

def get_d():
    global db
    if st.session_state.db_type == 'SQLite':
        db = SQLDatabase.from_uri(f"sqlite:///./{st.session_state.db_details}")
    elif st.session_state.db_type == 'MySQL':
        db = SQLDatabase.from_uri(f"{st.session_state.db_details}")
    elif st.session_state.db_type == 'SQL Server':
        db = SQLDatabase.from_uri(f"{st.session_state.db_details}")
    return db.dialect


def extract_sql(text):
    code_pattern = r'```(?:[^\n]*\n)+?([^`]+)(?:```|$)'
    match = re.search(code_pattern, text, re.DOTALL)
    return match.group(1) if match else None


def markdown_to_sql(markdown_code):
    code_pattern = r'```([a-zA-Z]+)\n(.*?)\n```'
    code_blocks = re.findall(code_pattern, markdown_code, re.DOTALL)
    sql_code_blocks = []
    for lang, code in code_blocks:
        sql_code_blocks.append(f'```sql\n{code}\n```')
    return '\n'.join(sql_code_blocks)

def get_dataframe_info(df):
    info = {
        "shape": df.shape,
        "columns": df.columns.tolist(),
        "dtypes": df.dtypes.to_dict(),
        "head": df.head().to_json(orient='records', lines=True),
        "tail": df.tail().to_json(orient='records', lines=True),
        "isna": df.isna().sum().to_dict()
    }
    return info

def extract_code_without_blocks(string):
    code_pattern = r'```(?:[^\n]*\n)+?([^`]+)(?:```|$)'
    code_matches = re.findall(code_pattern, string)
    return '\n'.join(code_matches)

def get_duckdb_schema_for_llm(db_connection):
    """
    Extracts the DuckDB schema in a format suitable for LLMs.

    Args:
        db_connection: A DuckDB connection object.

    Returns:
        A JSON string representing the schema or None if the database is empty.
    """

    table_names = [row[0] for row in db_connection.execute(
        "PRAGMA show_tables").fetchall()]

    if not table_names:
        return None  # Database is empty

    schema = {}

    for table_name in table_names:
        table_info = db_connection.execute(
            f"PRAGMA table_info('{table_name}')").fetchall()
        columns = []

        for column in table_info:
            column_data = {
                "name": column[1],
                "type": column[2],
                # Convert notnull to nullable (easier for LLMs)
                "nullable": not column[3],
                # Handle potential None values
                "default_value": column[4] if column[4] is not None else None,
                "primary_key": bool(column[5])  # Convert int to boolean
            }
            columns.append(column_data)

        schema[table_name] = {"columns": columns}

    return json.dumps(schema, indent=4)











