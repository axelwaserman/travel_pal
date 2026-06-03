"""Docker availability detection shared between conftest and test modules."""
import subprocess

#: Wall-clock budget for the ``docker info`` probe used to detect a daemon.
_DOCKER_PROBE_TIMEOUT_S: float = 5.0


def docker_is_available() -> bool:
    """Return True when a Docker daemon is reachable."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=_DOCKER_PROBE_TIMEOUT_S,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


#: Module-level constant evaluated once at import time.
DOCKER_AVAILABLE: bool = docker_is_available()
