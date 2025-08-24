from aicostmanager.delivery import ImmediateDelivery, PersistentDelivery
from aicostmanager.ini_manager import IniManager


def test_immediate_ini_over_env(tmp_path, monkeypatch):
    ini_path = tmp_path / "AICM.INI"
    monkeypatch.setenv("AICM_INI_PATH", str(ini_path))
    # Environment provides one value, INI overrides it
    monkeypatch.setenv("AICM_API_BASE", "https://env.example")
    monkeypatch.setenv("AICM_IMMEDIATE_PAUSE_SECONDS", "1")
    ini = IniManager(str(ini_path))
    ini.set_option("tracker", "AICM_API_BASE", "https://ini.example")
    ini.set_option("tracker", "AICM_IMMEDIATE_PAUSE_SECONDS", "2")

    delivery = ImmediateDelivery()

    assert delivery.api_base == "https://ini.example"
    assert delivery.immediate_pause_seconds == 2.0


def test_persistent_ini_over_env(tmp_path, monkeypatch):
    ini_path = tmp_path / "AICM.INI"
    monkeypatch.setenv("AICM_INI_PATH", str(ini_path))
    monkeypatch.setenv("AICM_API_BASE", "https://env.example")
    ini = IniManager(str(ini_path))
    ini.set_option("tracker", "AICM_API_BASE", "https://ini.example")

    delivery = PersistentDelivery(db_path=str(tmp_path / "queue.db"))
    try:
        assert delivery.api_base == "https://ini.example"
    finally:
        delivery.stop()


def test_env_db_path_over_default(tmp_path, monkeypatch):
    custom_db = tmp_path / "custom_queue.db"
    monkeypatch.setenv("AICM_DB_PATH", str(custom_db))
    monkeypatch.setenv("AICM_INI_PATH", str(tmp_path / "AICM.INI"))

    delivery = PersistentDelivery()
    try:
        assert delivery.db_path == str(custom_db)
        from pathlib import Path
        default_db = Path.home() / ".cache" / "aicostmanager" / "delivery_queue.db"
        assert delivery.db_path != str(default_db)
    finally:
        delivery.stop()

