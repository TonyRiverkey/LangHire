from core.browser_profile import cookies_path


def test_finds_current_and_legacy_cookie_locations(tmp_path):
    legacy = tmp_path / "Default" / "Cookies"
    assert cookies_path(tmp_path) == legacy
    legacy.parent.mkdir()
    legacy.touch()
    assert cookies_path(tmp_path) == legacy
    network = tmp_path / "Default" / "Network" / "Cookies"
    network.parent.mkdir()
    network.touch()
    assert cookies_path(tmp_path) == network

def test_migrates_modern_chromium_cookies(data_dir):
    from api.auth import browser_profile_dir

    old = data_dir / "browser_profile_collect"
    cookie_db = old / "Default" / "Network" / "Cookies"
    cookie_db.parent.mkdir(parents=True)
    cookie_db.write_bytes(b"existing profile cookie database")
    current = browser_profile_dir()
    assert cookies_path(current).read_bytes() == cookie_db.read_bytes()
    assert cookie_db.exists()
