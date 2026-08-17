# ADR 0004: Distribution name

Date: 2026-08-17

## Status

Accepted. Supersedes the distribution-name decision in ADR 0001; every other decision there stands.

## Context

ADR 0001 set the distribution name to `pyblackboard`, chosen because the name `blackboard` on PyPI is held by an unrelated package. The maintainer rejected the `py` prefix before first publication: the ecosystem's own tooling already marks a package as Python, and current libraries do not carry the prefix.

## Decision

The distribution publishes to PyPI as `blackboardx`. The import name stays `blackboard`. The `x` suffix is the pattern a Python library takes when its plain name is held, as in `httpx` and `networkx`.

## Consequences

- `pyproject.toml`, the lockfile, the README, the bug-report template, and the release-please configuration carry the new name in one change.
- Nothing was published under `pyblackboard`, so no PyPI transition, deprecation, or redirect exists.

## Alternatives rejected

- `pyblackboard`: the prefix is dated, and the maintainer rejected it.
- Brand names such as `slateboard` or `commonground`: they read as product names, not as a library named for its concept.
- Descriptive compounds such as `blackboard-agents` or `multiagent-blackboard`: longer, and the suffix form already disambiguates.
