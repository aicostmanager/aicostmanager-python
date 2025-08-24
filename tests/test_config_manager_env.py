from aicostmanager.config_manager import ConfigManager
from aicostmanager.ini_manager import IniManager


def test_env_var_overrides_default(monkeypatch, tmp_path):
    default = IniManager.resolve_path()
    env_path = tmp_path / "custom.ini"
    monkeypatch.setenv("AICM_INI_PATH", str(env_path))
    cfg = ConfigManager(load=False)
    assert cfg.ini_path == str(env_path)
    assert cfg.ini_path != default
