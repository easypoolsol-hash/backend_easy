#!/usr/bin/env python3
"""
MyPy runner script for pre-commit hooks.
Changes to the app directory and runs mypy with proper configuration.
"""

import os
import subprocess  # nosec B404
import sys


def main():
    # Change to the app directory (parent of config directory)
    config_dir = os.path.dirname(__file__)
    project_root = os.path.join(config_dir, "..")

    # Ensure the project root is on sys.path so imports like `app.*` or
    # `utils.*` resolve correctly regardless of the current working dir.
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # Change to the app directory (parent of config directory) for relative
    # mypy path arguments to work as before.
    app_dir = os.path.join(config_dir, "..", "app")
    os.chdir(app_dir)

    # Run mypy with the config file from config directory
    config_file = os.path.join(os.path.dirname(__file__), "mypy.ini")
    cmd = [
        sys.executable,
        "-m",
        "mypy",
        "--config-file",
        config_file,
        "bus_kiosk_backend/",
        "buses/",
        "events/",
        "kiosks/",
        "students/",
        "users/",
    ]

    # Run subprocess without shell to avoid shell injection risks.
    # Marked nosec because args are controlled by the repository and
    # this script is used in CI.
    result = subprocess.run(cmd, check=False)  # nosec
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
