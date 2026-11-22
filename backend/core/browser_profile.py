"""Locate Chromium's cookie database across profile layout versions."""
from pathlib import Path


def cookies_path(profile_dir):
    default = Path(profile_dir) / "Default"
    network = default / "Network" / "Cookies"
    return network if network.exists() else default / "Cookies"
