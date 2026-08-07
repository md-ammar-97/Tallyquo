from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from tallyquo.core.config import get_settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Migrations run raw SQL via op.execute() (roles, RLS policies, enums,
# exclusion constraints aren't idiomatic autogenerate territory) so there is
# no ORM metadata to diff against.
target_metadata = None


def get_url() -> str:
    # Migrations always run as the admin role — creating roles, enabling
    # RLS, and defining policies are operations the low-privilege app role
    # must never be able to perform (ADR-001).
    return get_settings().database_admin_url


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
