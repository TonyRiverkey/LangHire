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
