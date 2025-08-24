from aicostmanager import Tracker
from aicostmanager.ini_manager import IniManager


def test_immediate_timeout_ini_over_env(tmp_path, monkeypatch):
    ini_path = tmp_path / "AICM.INI"
    ini = IniManager(str(ini_path))
    ini.set_option("tracker", "AICM_TIMEOUT", "1.23")
    monkeypatch.setenv("AICM_TIMEOUT", "9.87")

    tracker = Tracker(aicm_api_key="test", ini_path=str(ini_path))
    try:
        assert tracker.delivery.timeout == 1.23
    finally:
        tracker.close()


def test_immediate_timeout_env_over_default(tmp_path, monkeypatch):
    ini_path = tmp_path / "AICM.INI"
    IniManager(str(ini_path))
    monkeypatch.setenv("AICM_TIMEOUT", "9.87")

    tracker = Tracker(aicm_api_key="test", ini_path=str(ini_path))
    try:
        assert tracker.delivery.timeout == 9.87
    finally:
        tracker.close()


def test_persistent_poll_interval_ini_over_env(tmp_path, monkeypatch):
    ini_path = tmp_path / "AICM.INI"
    ini = IniManager(str(ini_path))
    ini.set_option("tracker", "AICM_DB_PATH", str(tmp_path / "queue.db"))
    ini.set_option("tracker", "AICM_POLL_INTERVAL", "5.0")
    monkeypatch.setenv("AICM_POLL_INTERVAL", "7.0")

    tracker = Tracker(aicm_api_key="test", ini_path=str(ini_path))
    try:
        assert tracker.delivery.poll_interval == 5.0
    finally:
        tracker.close()


def test_persistent_poll_interval_env_over_default(tmp_path, monkeypatch):
    ini_path = tmp_path / "AICM.INI"
    ini = IniManager(str(ini_path))
    ini.set_option("tracker", "AICM_DB_PATH", str(tmp_path / "queue.db"))
    monkeypatch.setenv("AICM_POLL_INTERVAL", "7.0")

    tracker = Tracker(aicm_api_key="test", ini_path=str(ini_path))
    try:
        assert tracker.delivery.poll_interval == 7.0
    finally:
        tracker.close()
