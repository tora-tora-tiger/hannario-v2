from dataclasses import dataclass


@dataclass(frozen=True)
class LettaDbToolSpec:
    name: str
    description: str
    source_code: str
    return_char_limit: int = 12000
    tags: tuple[str, ...] = ("hannario", "db", "sqlite", "read-only")
    default_requires_approval: bool = False


RUN_READONLY_SQL_SOURCE = r'''DB_PATH = globals().get("DB_PATH", "/data/local.sqlite3")


def run_readonly_sql(sql: str, limit: int = 50) -> str:
    """Run a read-only SQL query against the local SQLite database.

    This tool is also safe to call for validation tests with unsafe-looking SQL.
    Non-read-only statements are rejected before execution.

    Args:
        sql: SQL to validate and run if it is read-only. Use SELECT, WITH, or safe
            PRAGMA introspection. Write statements are rejected without execution.
        limit: Maximum number of rows to return. Values are clamped to 1..200.

    Returns:
        A compact text result with column names and rows.
    """
    import sqlite3
    from pathlib import Path

    query = str(sql or "").strip()
    if not query:
        return "Failed to run SQL: sql is required."

    safe_limit = max(1, min(int(limit), 200))
    lowered = query.lower().lstrip()
    safe_starts = (
        "select ",
        "select\n",
        "with ",
        "with\n",
        "pragma table_info",
        "pragma table_list",
        "pragma index_list",
        "pragma foreign_key_list",
    )
    if not lowered.startswith(safe_starts):
        return "Rejected SQL: only SELECT, WITH, and safe PRAGMA introspection are allowed."

    stripped_semicolon = query.rstrip()
    if ";" in stripped_semicolon.rstrip(";"):
        return "Rejected SQL: multiple statements are not allowed."

    path = Path(DB_PATH)
    if not path.exists():
        return f"No SQLite database is available at {path}."

    uri = f"file:{path}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA query_only = ON")
            cursor = connection.execute(query)
            columns = [description[0] for description in cursor.description or []]
            rows = cursor.fetchmany(safe_limit + 1)
        finally:
            connection.close()
    except sqlite3.Error as error:
        return f"Failed to run SQL: {error}"

    if not columns:
        return "SQL completed but returned no columns."

    displayed_rows = rows[:safe_limit]
    lines = [
        "sql_result:",
        "columns: " + ", ".join(columns),
        f"row_count: {len(displayed_rows)}" + ("+" if len(rows) > safe_limit else ""),
    ]
    for row in displayed_rows:
        values = []
        for column in columns:
            value = row[column]
            values.append(f"{column}={value!r}")
        lines.append("- " + ", ".join(values))
    return "\n".join(lines)
'''


LETTA_DB_TOOL_SPECS = [
    LettaDbToolSpec(
        name="run_readonly_sql",
        description=(
            "Validate and run a read-only SQL query against the local SQLite database. "
            "Call this tool for safety tests too; unsafe write statements are rejected "
            "by the tool before execution."
        ),
        source_code=RUN_READONLY_SQL_SOURCE,
    ),
]
