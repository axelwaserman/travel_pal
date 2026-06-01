import sqlglot
from pathlib import Path


def transpile_sql(ansi_sql: str) -> str:
    """Transpile ANSI SQL to DuckDB dialect."""
    statements = sqlglot.transpile(ansi_sql, read="", write="duckdb")
    return ";\n".join(statements)


def _contains_jinja(sql: str) -> bool:
    """Check if SQL contains dbt Jinja template syntax."""
    return "{{" in sql or "{%" in sql


def transpile_directory(src: Path, dst: Path) -> None:
    """Transpile all .sql files from src directory to dst directory.

    Skips files containing dbt Jinja template syntax ({{ }} or {% %}).
    These are dbt model files not meant for direct browser transpilation.
    """
    dst.mkdir(parents=True, exist_ok=True)
    skipped = []
    for sql_file in src.rglob("*.sql"):
        content = sql_file.read_text()
        if _contains_jinja(content):
            skipped.append(sql_file.name)
            continue
        transpiled = transpile_sql(content)
        out_file = dst / sql_file.name
        out_file.write_text(transpiled)
    if skipped:
        print(f"Skipped {len(skipped)} dbt Jinja files: {', '.join(skipped)}")


if __name__ == "__main__":
    import sys
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("pipeline/transforms/models")
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("frontend/public/sql")
    transpile_directory(src, dst)
    print(f"Transpiled SQL from {src} → {dst}")
