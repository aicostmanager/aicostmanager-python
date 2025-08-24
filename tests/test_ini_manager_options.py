from aicostmanager.ini_manager import IniManager


def test_ini_manager_set_get(tmp_path):
    ini_path = tmp_path / "AICM.INI"
    mgr = IniManager(str(ini_path))
    mgr.set_option("tracker", "AICM_DELIVERY_TYPE", "PERSISTENT_QUEUE")
    assert (
        mgr.get_option("tracker", "AICM_DELIVERY_TYPE") == "PERSISTENT_QUEUE"
    )
