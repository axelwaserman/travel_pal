import sqlglot
from pathlib import Path


def transpile_sql(ansi_sql: str) -> str:
    """Transpile ANSI SQL to DuckDB dialect."""
    statements = sqlglot.transpile(ansi_sql, read="", write="duckdb")
    return ";\n".join(statements)


def transpile_directory(src: Path, dst: Path) -> None:
    """Transpile all .sql files from src directory to dst directory."""
    dst.mkdir(parents=True, exist_ok=True)
    for sql_file in src.rglob("*.sql"):
        transpiled = transpile_sql(sql_file.read_text())
        out_file = dst / sql_file.name
        out_file.write_text(transpiled)


if __name__ == "__main__":
    import sys
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("pipeline/transforms/models")
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("frontend/public/sql")
    transpile_directory(src, dst)
    print(f"Transpiled SQL from {src} → {dst}")
