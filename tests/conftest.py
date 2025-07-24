import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import os

import pytest
from dotenv import load_dotenv

# Load .env file from the current directory (sdks/python/tests)
ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(ENV_PATH, override=True)

# Debug prints to confirm environment variable loading
print("AICM_API_KEY (pre-force):", os.environ.get("AICM_API_KEY"))
print("AICM_API_BASE:", os.environ.get("AICM_API_BASE"))
print("AICM_INI_PATH:", os.environ.get("AICM_INI_PATH"))
print("OPENAI_API_KEY (pre-force):", os.environ.get("OPENAI_API_KEY"))


@pytest.fixture(scope="session", autouse=True)
def force_api_keys():
    # Always force the .env value for AICM_API_KEY and OPENAI_API_KEY
    from dotenv import load_dotenv

    ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(ENV_PATH, override=True)
    aicm_key = os.environ.get("AICM_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    if not aicm_key:
        pytest.skip("AICM_API_KEY not set in .env file")
    if not openai_key:
        print("WARNING: OPENAI_API_KEY not set in .env file (some tests may skip)")
    os.environ["AICM_API_KEY"] = aicm_key
    os.environ["OPENAI_API_KEY"] = openai_key or ""
    print("AICM_API_KEY (forced):", os.environ.get("AICM_API_KEY"))
    print("OPENAI_API_KEY (forced):", os.environ.get("OPENAI_API_KEY"))
    yield
    # Optionally clear after tests
    # del os.environ["AICM_API_KEY"]
    # del os.environ["OPENAI_API_KEY"]


@pytest.fixture(scope="session")
def aicm_api_key():
    return os.environ.get("AICM_API_KEY")


@pytest.fixture(scope="session")
def openai_api_key():
    return os.environ.get("OPENAI_API_KEY")


@pytest.fixture(scope="session")
def aicm_api_base():
    return os.environ.get("AICM_API_BASE", "https://aicostmanager.com")


@pytest.fixture(scope="session")
def aicm_ini_path(tmp_path_factory):
    ini_path = os.environ.get("AICM_INI_PATH")
    if ini_path:
        return ini_path
    # If not set, use a temp file
    tmp_dir = tmp_path_factory.mktemp("aicm_ini")
    return str(tmp_dir / "AICM.ini")


@pytest.fixture
def clean_delivery():
    """Reset global delivery state before each test to avoid pollution between tests."""
    from aicostmanager import delivery as mod

    # Store the current state
    original_delivery = getattr(mod, "_global_delivery", None)

    # Reset to clean state
    mod._global_delivery = None

    yield

    # Cleanup: stop any running delivery and reset
    if mod._global_delivery is not None:
        try:
            mod._global_delivery.stop()
        except Exception:
            pass
        mod._global_delivery = None
