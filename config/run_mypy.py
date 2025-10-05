#!/usr/bin/env python3
"""
MyPy runner script for pre-commit hooks.
Changes to the app directory and runs mypy with proper configuration.
"""

import os
import subprocess
import sys


def main():
    # Change to the app directory (parent of config directory)
    app_dir = os.path.join(os.path.dirname(__file__), "..", "app")
    os.chdir(app_dir)

    # Run mypy with the config file from config directory
    config_file = os.path.join(os.path.dirname(__file__), "mypy.ini")
    cmd = [sys.executable, "-m", "mypy", "--config-file", config_file, "bus_kiosk_backend/", "buses/", "events/", "kiosks/", "students/", "users/"]

    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
