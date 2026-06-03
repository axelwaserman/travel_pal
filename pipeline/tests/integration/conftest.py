"""Integration-test fixtures for Nessie + SeaweedFS Docker services.

Service start strategy
----------------------
If Nessie (``http://localhost:19120/iceberg/v1/config``) and SeaweedFS S3
(``localhost:8333``) are already responsive when the test session begins —
because the developer has the project stack running — the fixtures skip
``docker compose up`` and use the already-running services.  This avoids
port conflicts when the dev stack and the test suite run simultaneously.

The fixture injects ``NESSIE_S3_EXTERNAL_ENDPOINT=http://localhost:8333``
so Nessie vends a host-routable S3 endpoint to PyIceberg clients running
on the host (default vended endpoint targets the in-network hostname
``seaweedfs-s3``, which the host cannot resolve).

When the ports are *not* already in use, this module starts the infra
services itself via ``docker compose up`` (postgres, nessie, seaweedfs-*) and
registers a finaliser to tear them down via ``docker compose down -v``.

The dagster-webserver and dagster-daemon services carry ``profiles: ["app"]``
in docker-compose.yml and are therefore NOT started in either path.
"""
import os
import socket
import subprocess
import time
import urllib.request
from collections.abc import Callable, Generator
from pathlib import Path
from urllib.error import URLError

import pytest

from tests.integration._docker import DOCKER_AVAILABLE

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_REPO_ROOT: Path = Path(__file__).parent.parent.parent.parent  # …/travel_pal
_COMPOSE_FILE: str = str(_REPO_ROOT / "docker-compose.yml")
_TEST_PROJECT: str = "travelpal_test"
_DEV_PROJECT: str = "travel_pal"

NESSIE_HOST: str = "localhost"
NESSIE_PORT: int = 19120
S3_HOST: str = "localhost"
S3_PORT: int = 8333

_NESSIE_HEALTH_URL: str = (
    f"http://{NESSIE_HOST}:{NESSIE_PORT}/iceberg/v1/config?warehouse=warehouse"
)

# Probe / readiness budgets, hoisted so failure messages cannot drift.
_NESSIE_HEALTH_PROBE_TIMEOUT_S: float = 2.0
_TCP_PROBE_TIMEOUT_S: float = 2.0
_NESSIE_READY_TIMEOUT_S: float = 180.0
_NESSIE_READY_POLL_S: float = 3.0
_S3_READY_TIMEOUT_S: float = 60.0
_S3_READY_POLL_S: float = 2.0

# ---------------------------------------------------------------------------
# Readiness helpers
# ---------------------------------------------------------------------------


def _nessie_ready() -> bool:
    """Return True when Nessie's Iceberg REST /v1/config responds 200."""
    try:
        with urllib.request.urlopen(
            _NESSIE_HEALTH_URL, timeout=_NESSIE_HEALTH_PROBE_TIMEOUT_S
        ) as resp:
            return resp.status == 200
    except (URLError, OSError, TimeoutError):
        return False


def _tcp_open(host: str, port: int) -> bool:
    """Return True when a TCP connection to host:port succeeds."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(_TCP_PROBE_TIMEOUT_S)
        try:
            sock.connect((host, port))
            return True
        except OSError:
            return False


def _wait_for(check: Callable[[], bool], timeout: float, pause: float) -> bool:
    """Poll *check* callable until it returns True or *timeout* seconds pass."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return True
        time.sleep(pause)
    return False


def _compose_up(project: str) -> None:
    """Run ``docker compose up -d --wait`` for infra services.

    Sets ``NESSIE_S3_EXTERNAL_ENDPOINT`` so Nessie vends a host-routable
    S3 endpoint to PyIceberg clients running outside the Docker network.
    """
    env = {
        **os.environ,
        "NESSIE_S3_EXTERNAL_ENDPOINT": f"http://{S3_HOST}:{S3_PORT}",
    }
    subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            _COMPOSE_FILE,
            "-p",
            project,
            "up",
            "-d",
            "--wait",
            "postgres",
            "nessie",
            "seaweedfs-master",
            "seaweedfs-volume",
            "seaweedfs-filer",
            "seaweedfs-s3",
        ],
        check=True,
        env=env,
    )


def _compose_down(project: str) -> None:
    """Run ``docker compose down -v`` for the given project."""
    subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            _COMPOSE_FILE,
            "-p",
            project,
            "down",
            "-v",
        ],
        check=False,
    )


# ---------------------------------------------------------------------------
# Infrastructure lifecycle fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def infra_endpoints(request: pytest.FixtureRequest) -> Generator[dict[str, str], None, None]:
    """Yield Nessie and SeaweedFS S3 endpoint URLs once both services are ready.

    Skips the session when Docker is not available.

    If services are already responsive on their well-known ports (dev stack is
    running), they are reused without starting additional containers.
    Otherwise, this fixture starts the infra stack via ``docker compose up``
    and registers a teardown to ``docker compose down -v``.
    """
    if not DOCKER_AVAILABLE:
        pytest.skip("Docker daemon is not reachable — skipping integration tests.")

    services_preexisting = _nessie_ready() and _tcp_open(S3_HOST, S3_PORT)

    if not services_preexisting:
        # Start services ourselves and schedule teardown.
        _compose_up(_TEST_PROJECT)
        request.addfinalizer(lambda: _compose_down(_TEST_PROJECT))

    # Wait for application-level readiness regardless of who started the services.
    if not _wait_for(
        _nessie_ready,
        timeout=_NESSIE_READY_TIMEOUT_S,
        pause=_NESSIE_READY_POLL_S,
    ):
        pytest.fail(
            f"Nessie did not become responsive within {_NESSIE_READY_TIMEOUT_S} s."
        )

    if not _wait_for(
        lambda: _tcp_open(S3_HOST, S3_PORT),
        timeout=_S3_READY_TIMEOUT_S,
        pause=_S3_READY_POLL_S,
    ):
        pytest.fail(
            f"SeaweedFS S3 did not become responsive on :{S3_PORT} "
            f"within {_S3_READY_TIMEOUT_S} s."
        )

    # PyIceberg RestCatalog.url() appends "/v1/" to the uri, so "/iceberg/"
    # produces "/iceberg/v1/..." which is the Nessie Iceberg REST Catalog root.
    yield {
        "nessie_uri": f"http://{NESSIE_HOST}:{NESSIE_PORT}/iceberg/",
        "warehouse": "warehouse",
        "s3_endpoint": f"http://{S3_HOST}:{S3_PORT}",
        "s3_access_key": "admin",
        "s3_secret_key": "admin",
    }


# ---------------------------------------------------------------------------
# SeaweedFS bucket initialisation
# ---------------------------------------------------------------------------


def _detect_project() -> str:
    """Return the compose project name that has seaweedfs-master running."""
    for project in (_TEST_PROJECT, _DEV_PROJECT):
        result = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                _COMPOSE_FILE,
                "-p",
                project,
                "ps",
                "--services",
                "--filter",
                "status=running",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if "seaweedfs-master" in result.stdout:
            return project
    return _TEST_PROJECT  # fallback


@pytest.fixture(scope="session")
def seaweedfs_init(infra_endpoints: dict[str, str]) -> None:  # noqa: ARG001
    """Run scripts/seaweedfs/init.sh inside the running seaweedfs-master container.

    Idempotent: safe to call even if buckets already exist.
    """
    init_script = (_REPO_ROOT / "scripts" / "seaweedfs" / "init.sh").read_text(
        encoding="utf-8"
    )
    project = _detect_project()
    subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            _COMPOSE_FILE,
            "-p",
            project,
            "exec",
            "-T",
            "seaweedfs-master",
            "sh",
            "-c",
            init_script,
        ],
        check=True,
    )
