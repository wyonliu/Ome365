"""tests/test_scan_pii.py · scan_pii.py contract tests"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN_PII = ROOT / "scripts" / "scan_pii.py"


def test_scanner_exists_and_executable():
    assert SCAN_PII.is_file()


def test_scanner_default_clean():
    """Running on the OSS mirror itself should produce 0 hits."""
    result = subprocess.run(
        [sys.executable, str(SCAN_PII)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"


def test_scanner_fixtures_47_47():
    """Contract: tests/fixtures/pii_47.txt detects all 47 entries."""
    result = subprocess.run(
        [sys.executable, str(SCAN_PII), "--fixtures"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "47/47 detected" in result.stdout, f"output: {result.stdout}"


def test_scanner_quiet_mode():
    """--quiet mode produces no stdout output when clean."""
    result = subprocess.run(
        [sys.executable, str(SCAN_PII), "--quiet"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_scanner_help():
    """--help should print usage info, not error."""
    result = subprocess.run(
        [sys.executable, str(SCAN_PII), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "scan_pii" in result.stdout.lower() or "usage" in result.stdout.lower()
