from core.browser_profile import cookies_path, uses_browser_profile


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


def test_cleanup_matches_exact_profile_on_windows_and_posix():
    assert uses_browser_profile([r'--user-data-dir="C:\Users\example\langhire\browser_profile"'],
                                "c:/users/example/langhire/browser_profile")
    assert uses_browser_profile(["--user-data-dir=/tmp/langhire/browser_profile"], "/tmp/langhire/browser_profile")
    assert not uses_browser_profile(["--user-data-dir=/tmp/langhire/browser_profile_backup"], "/tmp/langhire/browser_profile")
    assert not uses_browser_profile(["a command mentions /tmp/langhire/browser_profile"], "/tmp/langhire/browser_profile")
