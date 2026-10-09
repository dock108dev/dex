"""Install checksum-pinned standalone CI validators, without piping scripts to a shell."""

import argparse
import hashlib
import io
import platform
import tarfile
import urllib.request
from pathlib import Path

TOOLS = {
    "actionlint": {
        "version": "1.7.12",
        "repository": "rhysd/actionlint",
        "assets": {
            ("Linux", "x86_64"): (
                "actionlint_1.7.12_linux_amd64.tar.gz",
                "8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8",
            ),
            ("Darwin", "arm64"): (
                "actionlint_1.7.12_darwin_arm64.tar.gz",
                "aba9ced2dee8d27fecca3dc7feb1a7f9a52caefa1eb46f3271ea66b6e0e6953f",
            ),
        },
    },
    "gitleaks": {
        "version": "8.30.1",
        "repository": "gitleaks/gitleaks",
        "assets": {
            ("Linux", "x86_64"): (
                "gitleaks_8.30.1_linux_x64.tar.gz",
                "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb",
            ),
            ("Darwin", "arm64"): (
                "gitleaks_8.30.1_darwin_arm64.tar.gz",
                "b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5",
            ),
        },
    },
}


def install(name, destination):
    spec = TOOLS[name]
    key = (platform.system(), platform.machine())
    if key not in spec["assets"]:
        raise ValueError(f"No reviewed binary for {name} on {key}")
    asset, expected = spec["assets"][key]
    url = f"https://github.com/{spec['repository']}/releases/download/v{spec['version']}/{asset}"
    with urllib.request.urlopen(url, timeout=40) as response:
        data = response.read(30 * 1024 * 1024 + 1)
    if len(data) > 30 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f"{name} download exceeds size bound or checksum does not match")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        member = archive.getmember(name)
        if not member.isfile() or member.size > 50 * 1024 * 1024:
            raise ValueError("Expected regular executable missing")
        stream = archive.extractfile(member)
        if stream is None:
            raise ValueError("Missing executable bytes")
        binary = stream.read()
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / name
    target.write_bytes(binary)
    target.chmod(0o755)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tool", choices=sorted(TOOLS))
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    print(install(args.tool, args.destination.resolve()))
