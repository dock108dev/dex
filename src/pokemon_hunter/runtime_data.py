"""Resolve reviewed runtime inputs in a wheel or the explicit source layout.

Never search the working directory or an installation's private root. Missing
packaged inputs must fail visibly rather than borrow a checkout's local files.
"""

from pathlib import Path


def root():
    package = Path(__file__).resolve().parent
    packaged = package / "data"
    if packaged.is_dir():
        return packaged
    checkout = package.parents[1]
    if package.parent.name == "src" and (checkout / "pyproject.toml").is_file():
        return checkout
    raise FileNotFoundError("Reviewed runtime inputs are missing from this installation")
