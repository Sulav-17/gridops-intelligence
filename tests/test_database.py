"""Tests for the database foundation."""

from collections.abc import Generator

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from gridops.config import Settings
from gridops.database import (
    Base,
    check_database_connection,
    make_engine,
    make_session_factory,
    session_scope,
)


def test_base_metadata_uses_naming_convention() -> None:
    """The shared metadata has deterministic constraint naming rules."""

    primary_key_template = Base.metadata.naming_convention["pk"]
    foreign_key_template = Base.metadata.naming_convention["fk"]

    assert isinstance(primary_key_template, str)
    assert isinstance(foreign_key_template, str)
    assert primary_key_template == "pk_%(table_name)s"
    assert foreign_key_template.startswith("fk_")


def test_make_engine_uses_settings_database_url() -> None:
    """Engine creation uses the configured PostgreSQL URL."""

    settings = Settings(
        database_url=SecretStr("postgresql+psycopg://gridops:gridops@localhost:55432/gridops")
    )

    engine = make_engine(settings)

    try:
        assert engine.url.drivername == "postgresql+psycopg"
        assert engine.url.database == "gridops"
        assert engine.pool is not None
    finally:
        engine.dispose()


def test_make_session_factory_binds_engine() -> None:
    """The session factory is bound to the provided engine."""

    engine = create_engine("sqlite+pysqlite:///:memory:")

    try:
        session_factory = make_session_factory(engine)

        with session_factory() as session:
            assert session.bind is engine
            assert session.autoflush is False
            assert session.expire_on_commit is False
    finally:
        engine.dispose()


def test_session_scope_commits_successful_work() -> None:
    """The session scope commits successful operations."""

    engine = create_engine("sqlite+pysqlite:///:memory:")
    session_factory = make_session_factory(engine)

    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE example (id INTEGER PRIMARY KEY)"))

        with session_scope(session_factory) as session:
            session.execute(text("INSERT INTO example (id) VALUES (1)"))

        with engine.connect() as connection:
            result = connection.execute(text("SELECT COUNT(*) FROM example"))

            assert result.scalar_one() == 1
    finally:
        engine.dispose()


def test_session_scope_rolls_back_failed_work() -> None:
    """The session scope rolls back failed operations."""

    engine = create_engine("sqlite+pysqlite:///:memory:")
    session_factory = make_session_factory(engine)

    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE example (id INTEGER PRIMARY KEY)"))

        with pytest.raises(RuntimeError, match="rollback"):
            with session_scope(session_factory) as session:
                session.execute(text("INSERT INTO example (id) VALUES (1)"))
                raise RuntimeError("rollback")

        with engine.connect() as connection:
            result = connection.execute(text("SELECT COUNT(*) FROM example"))

            assert result.scalar_one() == 0
    finally:
        engine.dispose()


@pytest.fixture
def live_postgres_engine() -> Generator[Engine, None, None]:
    """Create an engine for the Docker-backed test database."""

    settings = Settings(
        database_url=SecretStr("postgresql+psycopg://gridops:gridops@localhost:55432/gridops_test")
    )
    engine = make_engine(settings)

    try:
        yield engine
    finally:
        engine.dispose()


@pytest.mark.integration
def test_check_database_connection_against_live_postgres(
    live_postgres_engine: Engine,
) -> None:
    """The connectivity check succeeds against the Docker PostgreSQL database."""

    assert check_database_connection(live_postgres_engine) is True
