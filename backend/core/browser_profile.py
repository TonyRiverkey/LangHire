"""Locate Chromium's cookie database across profile layout versions."""
from pathlib import Path


def cookies_path(profile_dir):
    default = Path(profile_dir) / "Default"
    network = default / "Network" / "Cookies"
    return network if network.exists() else default / "Cookies"


def uses_browser_profile(command, profile_dir):
    normalize = lambda path: str(path).strip('"').replace("\\", "/").rstrip("/").casefold()
    return any(arg.startswith("--user-data-dir=") and normalize(arg.split("=", 1)[1]) == normalize(profile_dir)
               for arg in command)
