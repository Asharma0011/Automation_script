import importlib.util
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent / "Drivers.py"

if not SCRIPT_PATH.exists():
    raise FileNotFoundError(f"Source file not found: {SCRIPT_PATH}")

spec = importlib.util.spec_from_file_location("driver_module", SCRIPT_PATH)
driver_create = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver_create)


def test_main_runs_real_flow():
    driver_create.main()