"""Regression test for migration `0025_stage_setting_trigger` (ADR-025) —
verifies the real Alembic migration chain correctly backfills every
pre-existing `StageSetting` row into exactly one `StageSettingTrigger`
row, without disturbing any existing identity, and that the downgrade path
restores the original columns with the original values.

Builds the schema by running the real Alembic migration chain up to
`0024_ssr_audit_fk_correction` (the revision immediately before this one),
inserts a `stage_setting_set`/`stage_setting` row via raw SQL at that
pre-ADR-025 schema shape (the ORM models no longer have the old
`threshold_value`/`threshold_unit`/`time_delay_ms` columns on
`StageSetting`, so the ORM cannot be used to seed this state), then
upgrades to head and inspects the result with raw SQL. Mirrors
`test_ufls_migration_regression.py`'s own "build via `alembic upgrade`,
not `Base.metadata.create_all()`" discipline and its skip-if-no-Postgres
convention — several migrations in the chain predate this one and are not
guaranteed SQLite-compatible.
"""

from __future__ import annotations

import os
import uuid

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command
from app.core.config import get_settings
from app.db.base import Base

_POSTGRES_TEST_URL = os.environ.get("GRIDDEFENCE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not _POSTGRES_TEST_URL,
    reason="Requires a real PostgreSQL database (GRIDDEFENCE_TEST_DATABASE_URL) "
    "to exercise the real Alembic migration chain, not Base.metadata.create_all().",
)


def _alembic_config_root() -> str:
    # backend/tests/ -> backend/
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _alembic_config() -> Config:
    alembic_cfg = Config(os.path.join(_alembic_config_root(), "alembic.ini"))
    alembic_cfg.set_main_option("script_location", os.path.join(_alembic_config_root(), "alembic"))
    return alembic_cfg


def test_0025_backfills_existing_stage_settings_into_one_trigger_each() -> None:
    previous_database_url = os.environ.get("DATABASE_URL")
    engine = create_engine(_POSTGRES_TEST_URL)
    # Mirrors `test_ufls_migration_regression.py`'s own established
    # clean-slate discipline: drop `alembic_version` explicitly (not part
    # of `Base.metadata`), then drop every table `Base.metadata` currently
    # describes. `Base.metadata` still names `stage_setting_set` and
    # `stage_setting` (fewer columns now) and the new `stage_setting_
    # trigger`, so this still removes them if left over from a prior run.
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    Base.metadata.drop_all(bind=engine)

    try:
        os.environ["DATABASE_URL"] = _POSTGRES_TEST_URL
        get_settings.cache_clear()

        alembic_cfg = _alembic_config()
        command.upgrade(alembic_cfg, "0024_ssr_audit_fk_correction")

        # Seed one Stage Setting Set + one Stage Setting at the pre-ADR-025
        # schema shape via raw SQL (bootstrap a fake user row first — both
        # tables have real, enforced FKs to `user.user_id`).
        set_id = uuid.uuid4()
        stage_id = uuid.uuid4()
        user_id = uuid.uuid4()
        with engine.begin() as conn:
            conn.execute(
                text(
                    'INSERT INTO "user" (user_id, username, display_name, password_hash, status) '
                    "VALUES (:user_id, 'migration_test_user', 'Migration Test User', 'x', 'active')"
                ),
                {"user_id": user_id},
            )
            conn.execute(
                text(
                    "INSERT INTO stage_setting_set "
                    "(stage_setting_set_id, scheme_type, description, status, "
                    "created_by_user_id, updated_by_user_id) "
                    "VALUES (:id, 'UFLS', 'Pre-ADR-025 seed', 'PUBLISHED', :user_id, :user_id)"
                ),
                {"id": set_id, "user_id": user_id},
            )
            conn.execute(
                text(
                    "INSERT INTO stage_setting "
                    "(stage_setting_id, stage_setting_set_id, stage_order, "
                    "threshold_value, threshold_unit, time_delay_ms, region_scope_id) "
                    "VALUES (:id, :set_id, 1, 49.5000, 'Hz', 200, NULL)"
                ),
                {"id": stage_id, "set_id": set_id},
            )

        command.upgrade(alembic_cfg, "head")

        table_names = set(inspect(engine).get_table_names())
        assert "stage_setting_trigger" in table_names

        with engine.connect() as conn:
            stage_columns = {c["name"] for c in inspect(engine).get_columns("stage_setting")}
            assert "threshold_value" not in stage_columns
            assert "threshold_unit" not in stage_columns
            assert "time_delay_ms" not in stage_columns

            # Identity preserved — same stage_setting_id, same
            # stage_setting_set_id, same stage_order.
            stage_row = conn.execute(
                text(
                    "SELECT stage_setting_id, stage_setting_set_id, stage_order "
                    "FROM stage_setting WHERE stage_setting_id = :id"
                ),
                {"id": stage_id},
            ).one()
            assert stage_row.stage_setting_id == stage_id
            assert stage_row.stage_setting_set_id == set_id
            assert stage_row.stage_order == 1

            trigger_rows = conn.execute(
                text(
                    "SELECT trigger_order, threshold_value, threshold_unit, time_delay_ms "
                    "FROM stage_setting_trigger WHERE stage_setting_id = :id"
                ),
                {"id": stage_id},
            ).all()
            assert len(trigger_rows) == 1
            assert trigger_rows[0].trigger_order == 1
            assert trigger_rows[0].threshold_value == pytest.approx(49.5)
            assert trigger_rows[0].threshold_unit == "Hz"
            assert trigger_rows[0].time_delay_ms == 200

        # Downgrade path: the original columns are restored with the
        # original values (round-trip verification, mirroring the manual
        # verification already performed against the real dev database).
        command.downgrade(alembic_cfg, "0024_ssr_audit_fk_correction")
        with engine.connect() as conn:
            restored = conn.execute(
                text(
                    "SELECT threshold_value, threshold_unit, time_delay_ms "
                    "FROM stage_setting WHERE stage_setting_id = :id"
                ),
                {"id": stage_id},
            ).one()
            assert restored.threshold_value == pytest.approx(49.5)
            assert restored.threshold_unit == "Hz"
            assert restored.time_delay_ms == 200

        # Re-upgrade leaves the chain at head, clean, for any subsequent
        # test relying on the same database.
        command.upgrade(alembic_cfg, "head")

    finally:
        get_settings.cache_clear()
        if previous_database_url is not None:
            os.environ["DATABASE_URL"] = previous_database_url
        else:
            os.environ.pop("DATABASE_URL", None)
        get_settings.cache_clear()
