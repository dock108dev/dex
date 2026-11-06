"""Identity distinctions using authored metadata, never price coverage."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pokemon_hunter.beta import catalog_variants  # noqa: E402
from scripts.lv02_identity_audit import disposition  # noqa: E402


def child(descriptor):
    edition, finish, variant = catalog_variants.physical(descriptor)
    identity = dict(edition=edition, finish=finish, variant=variant)
    literal = dict(descriptor, thirdParty={"tcgplayer": 123})
    provenance = dict(variant_evidence=dict(descriptor=descriptor, source_descriptor=literal))
    return identity, provenance, [literal]


def test_numbered_parent_does_not_become_first_available_edition():
    identity = dict(edition=None, finish=None, variant=None)
    assert (
        disposition(identity, {}, [{"type": "holo"}, {"type": "holo", "stamp": ["1st-edition"]}])[0]
        == "ambiguous_numbered_parent"
    )


def test_single_availability_descriptor_does_not_assign_unspecified_parent():
    assert (
        disposition(dict(edition=None, finish=None, variant=None), {}, [{"type": "normal"}])[0]
        == "external_physical_metadata"
    )


def test_special_foil_is_represented_without_inventing_ordinary_finish():
    args = child({"type": "normal", "foil": "galaxy", "stamp": ["1st-edition"]})
    assert args[0]["finish"] is None
    assert disposition(*args)[0] == "locally_resolved_structured_finish"


@pytest.mark.parametrize(
    "descriptor", [{"type": "normal", "foil": "galaxy"}, {"type": "normal", "subtype": "1999-2000-copyright"}]
)
def test_missing_stamp_is_not_unlimited_or_not_applicable(descriptor):
    args = child(descriptor)
    assert disposition(*args)[0] == "external_edition_metadata"
    assert args[0]["edition"] is None


def test_ordinary_descriptor_needs_no_invented_extra_variant():
    assert disposition(*child({"type": "normal", "stamp": ["1st-edition"]}))[0] == "already_resolved"


def test_changed_physical_evidence_cannot_rebind_a_child():
    identity, provenance, english = child({"type": "normal", "stamp": ["1st-edition"]})
    identity["finish"] = "holo"
    with pytest.raises(ValueError, match="identity changed"):
        disposition(identity, provenance, english)
