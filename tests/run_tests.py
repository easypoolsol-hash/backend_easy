#!/usr/bin/env python
"""
Test Runner for Bus Kiosk Backend API
Run all tests or specific test categories.
"""

import os
from pathlib import Path
import subprocess
import sys

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

TESTS_DIR = "tests"

def run_command(command, description):
    """Run a command and return success status."""
    print(f"\n🔧 {description}")
    print(f"Command: {' '.join(command)}")
    try:
        result = subprocess.run(command, cwd=project_root, capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Success")
            return True
        else:
            print("❌ Failed")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def run_pytest_tests():
    """Run pytest tests."""
    return run_command([
        sys.executable, "-m", "pytest",
        TESTS_DIR,
        "-v",
        "--tb=short",
        "--disable-warnings"
    ], "Running pytest tests")

def run_standalone_tests():
    """Run standalone test files."""
    test_files = [
        os.path.join(project_root, TESTS_DIR, "test_health.py"),
        os.path.join(project_root, TESTS_DIR, "test_auth.py"),
        os.path.join(project_root, TESTS_DIR, "test_api_endpoints.py"),
        os.path.join(project_root, TESTS_DIR, "test_security.py"),
        os.path.join(project_root, TESTS_DIR, "test_openapi_schema.py")
    ]

    all_passed = True
    for test_file in test_files:
        if os.path.exists(test_file):
            success = run_command([
                sys.executable, test_file
            ], f"Running standalone tests in {test_file}")
            if not success:
                all_passed = False
        else:
            print(f"⚠️  Test file {test_file} not found")

    return all_passed

def run_django_tests():
    """Run Django test suite."""
    return run_command([
        sys.executable, "manage.py", "test",
        "--verbosity=2",
        "--keepdb"  # Keep test database for faster runs
    ], "Running Django tests")

def run_linting():
    """Run code linting."""
    commands = [
        ([sys.executable, "-m", "flake8", TESTS_DIR, "--max-line-length=100"], "Running flake8 linting"),
        ([sys.executable, "-m", "mypy", TESTS_DIR], "Running mypy type checking"),
    ]

    all_passed = True
    for command, description in commands:
        success = run_command(command, description)
        if not success:
            all_passed = False

    return all_passed

def main():
    """Main test runner."""
    print("🚀 Bus Kiosk Backend Test Suite")
    print("=" * 50)

    # Check if we're in the right directory
    if not os.path.exists("manage.py"):
        print("❌ Error: manage.py not found. Please run from project root.")
        sys.exit(1)

    # Parse command line arguments
    test_type = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

    # Define test runners
    test_runners = {
        "pytest": run_pytest_tests,
        "standalone": run_standalone_tests,
        "django": run_django_tests,
        "lint": run_linting,
    }

    success = True

    # Run tests based on type
    if test_type == "all":
        for runner in test_runners.values():
            if not runner():
                success = False
    else:
        runner = test_runners.get(test_type)
        if runner and not runner():
            success = False

    # Summary
    print("\n" + "=" * 50)
    if success:
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print("💥 Some tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
