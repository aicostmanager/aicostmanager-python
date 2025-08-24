from aicostmanager.client.base import BaseClient
from aicostmanager.ini_manager import IniManager


def test_base_client_ini_over_env(tmp_path, monkeypatch):
    ini_path = tmp_path / "AICM.INI"
    monkeypatch.setenv("AICM_API_BASE", "https://env.example")
    monkeypatch.setenv("AICM_API_URL", "/env")
    ini = IniManager(str(ini_path))
    ini.set_option("tracker", "AICM_API_BASE", "https://ini.example")
    ini.set_option("tracker", "AICM_API_URL", "/ini")

    client = BaseClient(aicm_api_key="key", aicm_ini_path=str(ini_path))

    assert client.api_base == "https://ini.example"
    assert client.api_url == "/ini"
