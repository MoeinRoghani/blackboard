"""The package imports, and every name in its public surface resolves."""

import blackboard


def test_package_imports() -> None:
    assert blackboard.__name__ == "blackboard"


def test_public_surface_is_declared_and_resolves() -> None:
    assert isinstance(blackboard.__all__, list)
    for name in blackboard.__all__:
        assert hasattr(blackboard, name)
