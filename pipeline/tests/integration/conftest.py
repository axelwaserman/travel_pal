"""Integration-test fixtures for Nessie + SeaweedFS Docker services.

Service start strategy
----------------------
If Nessie (``http://localhost:19120/api/v1/config``) and SeaweedFS S3
(``localhost:8333``) are already responsive when the test session begins —
because the developer has the project stack running — the fixtures skip
``docker compose up`` and use the already-running services.  This avoids
port conflicts when the dev stack and the test suite run simultaneously.

When the ports are *not* already in use, this module starts the infra
services itself via ``docker compose up`` (postgres, nessie, seaweedfs-*) and
registers a finaliser to tear them down via ``docker compose down -v``.

The ``docker_services``, ``docker_compose_file``, and related pytest-docker
fixtures are also overridden here so that, should any test use them directly,
they point at the correct compose file and project.

The dagster-webserver and dagster-daemon services carry ``profiles: ["app"]``
in docker-compose.yml and are therefore NOT started in either path.
"""
import subprocess
import time
import urllib.request
from collections.abc import Generator
from pathlib import Path

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

_NESSIE_HEALTH_URL: str = f"http://{NESSIE_HOST}:{NESSIE_PORT}/api/v1/config"

# ---------------------------------------------------------------------------
# pytest-docker fixture overrides (used if a test requests docker_services)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def docker_compose_file() -> str:
    """Point pytest-docker at the repo-root docker-compose.yml."""
    return _COMPOSE_FILE


@pytest.fixture(scope="session")
def docker_compose_project_name() -> str:
    """Stable project name keeps container names deterministic across runs."""
    return _TEST_PROJECT


@pytest.fixture(scope="session")
def docker_setup() -> list[str]:
    return [
        "up -d --wait postgres nessie seaweedfs-master seaweedfs-volume seaweedfs-filer seaweedfs-s3"
    ]


@pytest.fixture(scope="session")
def docker_cleanup() -> list[str]:
    return ["down -v"]


# ---------------------------------------------------------------------------
# Readiness helpers
# ---------------------------------------------------------------------------


def _nessie_ready() -> bool:
    """Return True when Nessie's /api/v1/config responds 200."""
    try:
        with urllib.request.urlopen(_NESSIE_HEALTH_URL, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def _tcp_open(host: str, port: int) -> bool:
    """Return True when a TCP connection to host:port succeeds."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(2)
        try:
            sock.connect((host, port))
            return True
        except OSError:
            return False


def _wait_for(check: object, timeout: float, pause: float) -> bool:
    """Poll *check* callable until it returns True or *timeout* seconds pass."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():  # type: ignore[operator]
            return True
        time.sleep(pause)
    return False


def _compose_up(project: str) -> None:
    """Run ``docker compose up -d --wait`` for infra services."""
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
    if not _wait_for(_nessie_ready, timeout=120.0, pause=3.0):
        pytest.fail("Nessie did not become responsive within 120 s.")

    if not _wait_for(lambda: _tcp_open(S3_HOST, S3_PORT), timeout=60.0, pause=2.0):
        pytest.fail("SeaweedFS S3 did not become responsive on :8333 within 60 s.")

    # PyIceberg RestCatalog.url() appends "/v1/" to the uri.  Use "/api/" as
    # the base so the constructed path is "/api/v1/config" not "/api/v1/v1/config".
    yield {
        "nessie_uri": f"http://{NESSIE_HOST}:{NESSIE_PORT}/api/",
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
