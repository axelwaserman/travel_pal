import pytest
from transpiler.transpile import transpile_sql, transpile_directory
from pathlib import Path


def test_transpile_cast_to_duckdb():
    ansi_sql = "SELECT CAST(first_seen AS TIMESTAMP) FROM flights"
    result = transpile_sql(ansi_sql)
    assert "TIMESTAMP" in result
    assert isinstance(result, str)
    assert len(result) > 0


def test_transpile_preserves_select_columns():
    ansi_sql = "SELECT icao24, callsign FROM stg_flights WHERE icao24 IS NOT NULL"
    result = transpile_sql(ansi_sql)
    assert "icao24" in result
    assert "callsign" in result
    assert "stg_flights" in result


def test_transpile_directory(tmp_path):
    sql_dir = tmp_path / "models"
    sql_dir.mkdir()
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (sql_dir / "test_model.sql").write_text(
        "SELECT CAST(x AS INTEGER) FROM t"
    )

    transpile_directory(sql_dir, out_dir)

    result_file = out_dir / "test_model.sql"
    assert result_file.exists()
    content = result_file.read_text()
    assert "SELECT" in content


def test_transpile_directory_skips_jinja(tmp_path):
    sql_dir = tmp_path / "models"
    sql_dir.mkdir()
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (sql_dir / "plain.sql").write_text("SELECT id FROM t")
    (sql_dir / "dbt_model.sql").write_text("SELECT id FROM {{ ref('t') }}")

    transpile_directory(sql_dir, out_dir)

    assert (out_dir / "plain.sql").exists()
    assert not (out_dir / "dbt_model.sql").exists()
