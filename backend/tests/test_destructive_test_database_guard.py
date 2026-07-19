"""Tests for `conftest.py`'s `_assert_safe_for_destructive_testing` — the
fail-closed guard added after the Development Database Recovery incident
(GRIDDEFENCE_TEST_DATABASE_URL was once pointed at the real development
database; this fixture's own `Base.metadata.drop_all()` teardown then
destroyed every application table in it).

Exercises the guard directly, against disposable SQLite files — never
against a real PostgreSQL database (that would defeat the point of testing
a *destructive-test* safety guard). `_assert_safe_for_destructive_testing`
is written to be dialect-agnostic (`sqlalchemy.inspect()`, not a raw
`information_schema` query) specifically so it can be exercised this way.
"""

from __future__ import annotations

import os

import pytest

import conftest as root_conftest


@pytest.fixture(autouse=True)
def _clear_acknowledgement_variable():
    """Every test below sets `GRIDDEFENCE_ALLOW_DESTRUCTIVE_TEST_DATABASE`
    explicitly where it matters — never inherit it from the real
    environment a developer's shell might have set for an actual
    PostgreSQL verification pass."""
    original = os.environ.pop("GRIDDEFENCE_ALLOW_DESTRUCTIVE_TEST_DATABASE", None)
    yield
    if original is not None:
        os.environ["GRIDDEFENCE_ALLOW_DESTRUCTIVE_TEST_DATABASE"] = original
    else:
        os.environ.pop("GRIDDEFENCE_ALLOW_DESTRUCTIVE_TEST_DATABASE", None)


def _sqlite_test_url(tmp_path, name: str) -> str:
    """A real, connectable, disposable SQLite file whose `make_url(...).database`
    is exactly `name` — mirrors a PostgreSQL database name closely enough to
    exercise the guard's own name-based checks against a real engine."""
    return f"sqlite:///{tmp_path / name}"


def test_rejects_database_name_not_ending_in_test_suffix(tmp_path):
    os.environ["GRIDDEFENCE_ALLOW_DESTRUCTIVE_TEST_DATABASE"] = "true"
    url = _sqlite_test_url(tmp_path, "engineering_platform_staging")

    with pytest.raises(RuntimeError, match="does not end in '_test'"):
        root_conftest._assert_safe_for_destructive_testing(url)


def test_rejects_database_matching_configured_database_url(tmp_path, monkeypatch):
    # SQLite's own `database` URL component is always a full file path, not
    # a bare name — both sides of the comparison must share that same path
    # for this test to exercise the check in an apples-to-apples way.
    shared_path_url = _sqlite_test_url(tmp_path, "some_dev_db")

    class _FakeSettings:
        database_url = shared_path_url

    monkeypatch.setattr(root_conftest, "get_settings", lambda: _FakeSettings())
    os.environ["GRIDDEFENCE_ALLOW_DESTRUCTIVE_TEST_DATABASE"] = "true"

    with pytest.raises(RuntimeError, match="identical to the application's own configured"):
        root_conftest._assert_safe_for_destructive_testing(shared_path_url)


def test_rejects_known_development_database_name(tmp_path, monkeypatch):
    class _FakeSettings:
        database_url = "postgresql+psycopg://x:x@localhost:5432/unrelated"

    monkeypatch.setattr(root_conftest, "get_settings", lambda: _FakeSettings())
    os.environ["GRIDDEFENCE_ALLOW_DESTRUCTIVE_TEST_DATABASE"] = "true"
    url = _sqlite_test_url(tmp_path, "engineering_platform")
    # `_KNOWN_DEVELOPMENT_DATABASE_NAMES` holds bare database names
    # ("engineering_platform"); SQLite's own `database` component is
    # always a full path, so the known-name set is patched to the exact
    # path this test's own URL produces — proving the mechanism itself
    # works, independent of SQLite-vs-PostgreSQL naming shape.
    known_names = frozenset({str(tmp_path / "engineering_platform")})
    monkeypatch.setattr(root_conftest, "_KNOWN_DEVELOPMENT_DATABASE_NAMES", known_names)

    with pytest.raises(RuntimeError, match="known GridDefence development database name"):
        root_conftest._assert_safe_for_destructive_testing(url)


def test_rejects_when_acknowledgement_variable_missing(tmp_path, monkeypatch):
    class _FakeSettings:
        database_url = "postgresql+psycopg://x:x@localhost:5432/unrelated"

    monkeypatch.setattr(root_conftest, "get_settings", lambda: _FakeSettings())
    url = _sqlite_test_url(tmp_path, "engineering_platform_test")

    with pytest.raises(RuntimeError, match="GRIDDEFENCE_ALLOW_DESTRUCTIVE_TEST_DATABASE"):
        root_conftest._assert_safe_for_destructive_testing(url)


def test_rejects_when_acknowledgement_variable_is_not_literally_true(tmp_path, monkeypatch):
    class _FakeSettings:
        database_url = "postgresql+psycopg://x:x@localhost:5432/unrelated"

    monkeypatch.setattr(root_conftest, "get_settings", lambda: _FakeSettings())
    os.environ["GRIDDEFENCE_ALLOW_DESTRUCTIVE_TEST_DATABASE"] = "yes"
    url = _sqlite_test_url(tmp_path, "engineering_platform_test")

    with pytest.raises(RuntimeError, match="GRIDDEFENCE_ALLOW_DESTRUCTIVE_TEST_DATABASE"):
        root_conftest._assert_safe_for_destructive_testing(url)


def test_rejects_nonempty_database_with_no_marker(tmp_path, monkeypatch):
    """A database that passes every naming/acknowledgement check but
    already has tables (created outside this fixture entirely) and no
    marker is refused — defense in depth against a database that merely
    happens to satisfy the naming convention by coincidence."""

    class _FakeSettings:
        database_url = "postgresql+psycopg://x:x@localhost:5432/unrelated"

    monkeypatch.setattr(root_conftest, "get_settings", lambda: _FakeSettings())
    os.environ["GRIDDEFENCE_ALLOW_DESTRUCTIVE_TEST_DATABASE"] = "true"
    url = _sqlite_test_url(tmp_path, "somebody_elses_test")

    from sqlalchemy import create_engine, text

    engine = create_engine(url)
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE unrelated_preexisting_table (id INTEGER)"))
        conn.commit()
    engine.dispose()

    with pytest.raises(RuntimeError, match="has never been provisioned with this fixture's own"):
        root_conftest._assert_safe_for_destructive_testing(url)


def test_accepts_and_provisions_marker_for_a_fresh_dedicated_test_database(tmp_path, monkeypatch):
    class _FakeSettings:
        database_url = "postgresql+psycopg://x:x@localhost:5432/unrelated"

    monkeypatch.setattr(root_conftest, "get_settings", lambda: _FakeSettings())
    os.environ["GRIDDEFENCE_ALLOW_DESTRUCTIVE_TEST_DATABASE"] = "true"
    url = _sqlite_test_url(tmp_path, "engineering_platform_test")

    root_conftest._assert_safe_for_destructive_testing(url)

    from sqlalchemy import create_engine, inspect

    engine = create_engine(url)
    try:
        assert root_conftest._TEST_DB_MARKER_TABLE in inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_accepts_a_database_already_carrying_the_marker_from_a_prior_run(tmp_path, monkeypatch):
    class _FakeSettings:
        database_url = "postgresql+psycopg://x:x@localhost:5432/unrelated"

    monkeypatch.setattr(root_conftest, "get_settings", lambda: _FakeSettings())
    os.environ["GRIDDEFENCE_ALLOW_DESTRUCTIVE_TEST_DATABASE"] = "true"
    url = _sqlite_test_url(tmp_path, "engineering_platform_test")

    # First run provisions the marker; second run must not re-raise even
    # though the database is no longer empty (it now holds the marker).
    root_conftest._assert_safe_for_destructive_testing(url)
    root_conftest._assert_safe_for_destructive_testing(url)


def test_error_message_never_contains_the_password(tmp_path):
    os.environ["GRIDDEFENCE_ALLOW_DESTRUCTIVE_TEST_DATABASE"] = "true"
    url = "postgresql+psycopg://engineering_app:super-secret-password@localhost:5432/not_a_test_db"

    with pytest.raises(RuntimeError) as exc_info:
        root_conftest._assert_safe_for_destructive_testing(url)

    assert "super-secret-password" not in str(exc_info.value)


def test_connection_summary_never_includes_password_or_username():
    summary = root_conftest._connection_summary(
        "postgresql+psycopg://engineering_app:super-secret-password@localhost:5432/engineering_platform"
    )
    assert "super-secret-password" not in summary
    assert "engineering_app" not in summary
    assert summary == "localhost:5432/engineering_platform"
