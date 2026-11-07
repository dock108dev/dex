"""Installed member verification reuses hashes, never changed file identities."""

import hashlib
import os

import pytest

from pokemon_hunter.beta import hunter_installed as installed


@pytest.fixture
def package(tmp_path, monkeypatch):
    root = tmp_path / "package"
    (root / "beta").mkdir(parents=True)
    module = root / "beta" / "hunter_installed.py"
    module.write_text("authored package identity fixture")
    (root / "member.py").write_text("AAAA")
    monkeypatch.setattr(installed, "__file__", str(module))
    installed._member_digest.cache_clear()
    yield root
    installed._member_digest.cache_clear()


def test_unchanged_members_reuse_hashes_and_same_length_rewrite_invalidates(package, monkeypatch):
    original = hashlib.file_digest
    calls = []

    def measured(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(hashlib, "file_digest", measured)
    first = installed.package_digest()
    assert len(calls) == 2
    assert installed.package_digest() == first and len(calls) == 2
    member = package / "member.py"
    before = member.stat()
    member.write_text("BBBB")
    os.utime(member, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert member.stat().st_size == before.st_size and member.stat().st_mtime_ns == before.st_mtime_ns
    assert installed.package_digest() != first and len(calls) == 3


def test_added_removed_and_symlinked_members_cannot_reuse_old_package_identity(package):
    first = installed.package_digest()
    extra = package / "new.py"
    extra.write_text("new member")
    assert installed.package_digest() != first
    extra.unlink()
    assert installed.package_digest() == first
    extra.symlink_to(package / "member.py")
    with pytest.raises(ValueError, match="identity is unavailable"):
        installed.package_digest()


def test_member_change_during_verification_is_rejected(package, monkeypatch):
    original = hashlib.file_digest

    def mutate(stream, algorithm):
        result = original(stream, algorithm)
        inode = os.fstat(stream.fileno()).st_ino
        for member in package.rglob("*.py"):
            if member.stat().st_ino == inode:
                member.write_text("changed")
                break
        return result

    monkeypatch.setattr(hashlib, "file_digest", mutate)
    with pytest.raises(ValueError, match="changed during verification"):
        installed.package_digest()


def test_directory_enumeration_preserves_all_members_and_refuses_linked_directory(package):
    import json

    nested = package / "assets" / "nested"
    nested.mkdir(parents=True)
    (nested / ".hidden").write_text("also an application member")
    (nested / "asset.svg").write_text("authored asset")
    cache = nested / "__pycache__"
    cache.mkdir()
    (cache / "ignored.pyc").write_bytes(b"interpreter cache")
    expected = {
        p.relative_to(package).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in package.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }
    assert (
        installed.package_digest()
        == hashlib.sha256(json.dumps(expected, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    )
    (package / "linked-assets").symlink_to(nested, target_is_directory=True)
    with pytest.raises(ValueError, match="identity is unavailable"):
        installed.package_digest()
