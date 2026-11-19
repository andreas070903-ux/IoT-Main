"""In-memory control state for the simulated turbines."""

from threading import Lock


TURBINE_IDS = ("WT-001", "WT-002", "WT-003")

_running = {turbine_id: True for turbine_id in TURBINE_IDS}
_lock = Lock()


def list_turbine_controls() -> list[dict[str, str]]:
    """Return the current simulated running state for every turbine."""
    with _lock:
        return [
            {
                "Turbine_ID": turbine_id,
                "status": "RUNNING" if _running[turbine_id] else "STOPPED",
            }
            for turbine_id in TURBINE_IDS
        ]


def get_turbine_control(turbine_id: str) -> dict[str, str]:
    """Return one turbine's simulated control state."""
    with _lock:
        if turbine_id not in _running:
            raise KeyError(turbine_id)
        return {
            "Turbine_ID": turbine_id,
            "status": "RUNNING" if _running[turbine_id] else "STOPPED",
        }


def set_turbine_running(turbine_id: str, running: bool) -> dict[str, str]:
    """Set one turbine's simulated running state."""
    with _lock:
        if turbine_id not in _running:
            raise KeyError(turbine_id)
        _running[turbine_id] = running
        return {
            "Turbine_ID": turbine_id,
            "status": "RUNNING" if running else "STOPPED",
        }


def turbine_is_stopped(turbine_id: str) -> bool:
    """Check whether a known turbine is stopped in the simulation."""
    with _lock:
        return turbine_id in _running and not _running[turbine_id]
