"""Disposable PostgreSQL pg_dump/pg_restore recovery exercise for CI."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url

from incident_atlas.db import engine
from incident_atlas.models import PilotWorkspace

pytestmark = pytest.mark.postgres


def _run(command: list[str], *, env: dict[str, str]) -> None:
    subprocess.run(command, env=env, check=True, capture_output=True, text=True)


def test_postgres_backup_restores_pilot_marker_in_disposable_database() -> None:
    docker = shutil.which("docker")
    if not docker:
        if os.getenv("CI"):
            pytest.fail("Docker is required for the CI backup restore verification.")
        pytest.skip("Docker is not available for the disposable backup restore check.")

    database_url = make_url(os.environ["DATABASE_URL"])
    password = database_url.password or ""
    user = database_url.username or ""
    host = database_url.host or "127.0.0.1"
    port = str(database_url.port or 5432)
    source_database = database_url.database or ""
    restored_database = f"restore_{uuid.uuid4().hex[:12]}"
    marker = f"restore-marker-{uuid.uuid4().hex}"
    client_env = {**os.environ, "PGPASSWORD": password}
    marker_time = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            PilotWorkspace.__table__.insert().values(
                id=marker, name="Disposable restore marker", created_at=marker_time
            )
        )

    admin_url = database_url.set(drivername="postgresql+psycopg", database="postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    restore_engine = None
    try:
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{restored_database}"')
        with tempfile.TemporaryDirectory(prefix="incident-atlas-backup-") as directory:
            dump_path = Path(directory) / "pilot.dump"
            common = [
                docker,
                "run",
                "--rm",
                "--network",
                "host",
                "-e",
                "PGPASSWORD",
                "-v",
                f"{directory}:/backup",
            ]
            _run(
                common
                + [
                    "--entrypoint",
                    "pg_dump",
                    "postgres:17",
                    "--format=custom",
                    "--no-owner",
                    "--no-privileges",
                    "--host",
                    host,
                    "--port",
                    port,
                    "--username",
                    user,
                    "--dbname",
                    source_database,
                    "--file",
                    "/backup/pilot.dump",
                ],
                env=client_env,
            )
            _run(
                [
                    docker,
                    "run",
                    "--rm",
                    "--network",
                    "host",
                    "-e",
                    "PGPASSWORD",
                    "-v",
                    f"{directory}:/backup",
                    "--entrypoint",
                    "pg_restore",
                    "postgres:17",
                    "--exit-on-error",
                    "--no-owner",
                    "--no-privileges",
                    "--host",
                    host,
                    "--port",
                    port,
                    "--username",
                    user,
                    "--dbname",
                    restored_database,
                    "/backup/pilot.dump",
                ],
                env=client_env,
            )
            assert dump_path.exists(), "pg_dump did not produce the requested archive"
        restore_url = database_url.set(
            drivername="postgresql+psycopg", database=restored_database
        )
        restore_engine = create_engine(restore_url)
        with restore_engine.connect() as connection:
            restored = connection.scalar(
                select(PilotWorkspace.id).where(PilotWorkspace.id == marker)
            )
            assert restored == marker
        print("Disposable PostgreSQL restore passed: pilot workspace marker recovered.")
    finally:
        if restore_engine is not None:
            restore_engine.dispose()
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(
                f'DROP DATABASE IF EXISTS "{restored_database}" WITH (FORCE)'
            )
        admin_engine.dispose()
        with engine.begin() as connection:
            connection.execute(
                PilotWorkspace.__table__.delete().where(PilotWorkspace.id == marker)
            )
