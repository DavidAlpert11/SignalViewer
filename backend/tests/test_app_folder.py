"""F15: one app folder, and the tests never write to the developer's real ~/.signalviewer."""
import os

SV_REAL_HOME = os.environ["SV_TEST_REAL_HOME"]


def _under(path: str, folder: str) -> bool:
    path, folder = os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.abspath(folder))
    return path == folder or path.startswith(folder + os.sep)


def test_the_tests_use_a_home_of_their_own():
    from app import common, fleet, prefs, push, store, tiles
    real = os.path.join(SV_REAL_HOME, ".signalviewer")
    for p in (prefs.APP_DIR, common.APP_DIR, common.AUTOSAVE, store.UPLOAD_DIR, fleet.DB_PATH,
              push.PUSH_FILE, tiles.CACHE, prefs.DEFAULT_TEMPLATE_DIR):
        assert not _under(p, real), p


def test_one_app_folder_for_every_module():
    from app import common, fleet, prefs, push, store, tiles
    for p in (common.APP_DIR, store.UPLOAD_DIR, fleet.DB_PATH, push.PUSH_FILE, tiles.CACHE):
        assert _under(p, prefs.APP_DIR), p
