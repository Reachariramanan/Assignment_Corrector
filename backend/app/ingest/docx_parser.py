import subprocess
from pathlib import Path


def docx_to_html(path: Path) -> str:
    result = subprocess.run(
        ["pandoc", str(path), "-t", "html", "--wrap=none"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def docx_to_plain(path: Path) -> str:
    result = subprocess.run(
        ["pandoc", str(path), "-t", "plain", "--wrap=none"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def docx_to_markdown(path: Path) -> str:
    result = subprocess.run(
        ["pandoc", str(path), "-t", "markdown", "--wrap=none"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout
