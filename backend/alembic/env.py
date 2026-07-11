"""Alembic environment.

Migrations are generated against `app.db.base.Base.metadata`. Every module's
`models.py` must be imported here once it exists, so its tables register with
`Base.metadata` before `--autogenerate` runs (docs/architecture/
implementation-plan.md §5 — autogenerate output is always reviewed, never
committed blindly).
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import get_settings
from app.db.base import Base

# --- Import every module's models here as modules are added -----------------
from app.modules.automatic_load_shedding_functionality import (  # noqa: F401
    models as automatic_load_shedding_functionality_models,
)
from app.modules.equipment_registry import models as equipment_registry_models  # noqa: F401
from app.modules.iam import models as iam_models  # noqa: F401
from app.modules.psse_integration import models as psse_integration_models  # noqa: F401
from app.modules.sensitive_customer_registry import (  # noqa: F401
    models as sensitive_customer_registry_models,
)
from app.modules.substation_registry import models as substation_registry_models  # noqa: F401
from app.reference_data import models as reference_data_models  # noqa: F401

# ------------------------------------------------------------------------------

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (generates SQL only)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
