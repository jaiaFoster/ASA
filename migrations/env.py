from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from asa.config import Settings

config = context.config
if config.config_file_name is not None:
    # SPRINT-013 S13-04B: disable_existing_loggers defaults to True, which
    # silently disables every logger already created in this process that
    # alembic.ini's own [loggers] section doesn't list (root/sqlalchemy/
    # alembic only) -- when command.upgrade() runs inside a pytest session
    # that has already imported application modules (any of them creating
    # their own logging.getLogger(__name__) at import time, e.g.
    # asa.portfolio_run), those loggers go dead for the rest of the
    # process. Confirmed directly: tests/asa/test_logging.py's own caplog
    # assertion started failing with zero captured records the moment a
    # Postgres-fixture test file that alphabetically runs before it
    # (tests/asa/test_historical_skew_postgres_integration.py) began
    # calling command.upgrade() first in the same pytest session -- not a
    # defect in that new file's own logic, a latent fragility here that
    # any future new test file sorting earlier than test_logging.py could
    # have re-triggered regardless. disable_existing_loggers=False keeps
    # alembic's own console logging working exactly as configured while
    # leaving every other logger in this process alone.
    fileConfig(config.config_file_name, disable_existing_loggers=False)
config.set_main_option("sqlalchemy.url", Settings().database_url)
target_metadata = None


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
