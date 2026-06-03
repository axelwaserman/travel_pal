"""Docker availability detection shared between conftest and test modules."""
import subprocess


def docker_is_available() -> bool:
    """Return True when a Docker daemon is reachable."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


#: Module-level constant evaluated once at import time.
DOCKER_AVAILABLE: bool = docker_is_available()
