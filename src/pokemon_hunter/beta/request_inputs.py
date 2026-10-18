"""Single-valued HTTP selectors shared by catalog and collection boundaries.

Validate multiplicity before converting Django's multi-value containers to a
plain mapping. Domain services still own values, scope and account authority.
"""


def single_values(values, allowed=None):
    if any(len(items) != 1 for _, items in values.lists()):
        raise ValueError("Choose each field once")
    raw = values.dict()
    if allowed is not None and set(raw) - allowed:
        raise ValueError("Unsupported request fields")
    return raw


def query(request, allowed=None):
    return single_values(request.GET, allowed)
