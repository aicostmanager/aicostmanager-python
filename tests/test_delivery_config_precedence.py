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

