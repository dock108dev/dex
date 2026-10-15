"""Prevent the staging gate from selecting owner or remote database state."""

import pytest

from scripts.ci.staging import disposable_url, environment


@pytest.mark.parametrize(
    "url",
    [
        None,
        "postgresql://127.0.0.1:5432/collection",
        "postgresql://remote.example:5432/dex_ci_test",
        "postgresql://127.0.0.1/dex_ci_test",
        "postgresql://127.0.0.1:1234/dex_ci_test?service=production",
        "sqlite:///dex_ci_test",
    ],
)
def test_staging_rejects_owner_remote_or_ambiguous_target_before_io(url):
    with pytest.raises(ValueError, match="explicit loopback CI"):
        disposable_url(url)


def test_staging_accepts_only_explicit_disposable_url_and_scrubs_provider_environment(monkeypatch):
    assert disposable_url("postgresql://fixture:fixture@127.0.0.1:5432/dex_ci_test")
    for key in ("DEX_B1_ROOT", "OPENAI_API_KEY", "EBAY_CLIENT_SECRET", "DATABASE_URL", "PGHOSTADDR"):
        monkeypatch.setenv(key, "excluded")
    selected = environment()
    assert not any(
        key in selected
        for key in ("DEX_B1_ROOT", "OPENAI_API_KEY", "EBAY_CLIENT_SECRET", "DATABASE_URL", "PGHOSTADDR")
    )
