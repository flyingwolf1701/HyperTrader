#!/usr/bin/env python
"""
Test runner script with coverage reporting.
Run all tests and generate coverage reports.
"""
import subprocess
import sys
import os


def run_tests():
    """Run all tests with coverage."""
    print("=" * 60)
    print("Running HyperTrader Test Suite with Coverage")
    print("=" * 60)

    # Set Python path to include src directory
    os.environ['PYTHONPATH'] = os.path.join(os.path.dirname(__file__), 'src')

    # Test commands
    commands = [
        # Run tests with coverage
        [
            "python", "-m", "pytest",
            "tests/",
            "-v",  # Verbose output
            "--tb=short",  # Shorter traceback
            "--cov=src",  # Coverage for src directory
            "--cov-report=term-missing",  # Terminal report with missing lines
            "--cov-report=html",  # HTML report
            "--cov-config=.coveragerc",  # Use coverage config
            "--hypothesis-show-statistics",  # Show hypothesis statistics
        ],
    ]

    for cmd in commands:
        print(f"\nRunning: {' '.join(cmd)}")
        print("-" * 40)

        result = subprocess.run(cmd, capture_output=False, text=True)

        if result.returncode != 0:
            print(f"\n❌ Tests failed with exit code {result.returncode}")
            return False

    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("\n📊 Coverage report generated in 'htmlcov/index.html'")
    print("=" * 60)

    # Run coverage report separately for summary
    subprocess.run(["python", "-m", "coverage", "report"], capture_output=False)

    return True


def run_specific_test(test_file):
    """Run a specific test file."""
    print(f"Running specific test: {test_file}")
    cmd = [
        "python", "-m", "pytest",
        test_file,
        "-v",
        "--tb=short",
        "--hypothesis-show-statistics"
    ]

    result = subprocess.run(cmd, capture_output=False, text=True)
    return result.returncode == 0


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Run specific test file
        success = run_specific_test(sys.argv[1])
    else:
        # Run all tests
        success = run_tests()

    sys.exit(0 if success else 1)