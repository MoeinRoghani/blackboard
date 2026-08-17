# ADR 0005: Publishing to PyPI

Date: 2026-08-17

## Status

Accepted

## Context

The distribution publishes to PyPI as `blackboardx`. PyPI accepts an upload authenticated in one of two ways. An API token is a long-lived string the uploader holds, whether on a maintainer's machine or in a repository secret. Trusted publishing instead verifies an OpenID Connect token that GitHub issues to one workflow in one repository, and returns a credential that expires with the upload.

The choice also decides what gets published. A maintainer uploading from a laptop publishes the working copy, which is the tagged commit only if the checkout happens to match it.

## Decision

The upload runs in `.github/workflows/publish.yml`, on a published GitHub release, authenticated by trusted publishing. No API token exists for this project.

The workflow builds from the tagged commit and refuses to upload when the tag names a version other than the one in the package metadata. Its `id-token: write` permission is granted on the publish job rather than at the top of the file, and no other workflow in the repository requests it.

## Consequences

- No credential exists to store, rotate, or leak. Compromising the maintainer's machine does not yield the ability to publish.
- What reaches PyPI is built from the commit the tag names, so the released artifact and the released source agree by construction.
- Publishing requires the deployment environment `pypi` in the repository and the matching publisher registered on PyPI. Renaming either breaks the upload until both agree.
- A release cannot be published from a laptop. That is the intent, and it means a maintainer without repository access cannot ship.

## Alternatives rejected

- **An API token in a repository secret.** The credential is long-lived, publishes under the maintainer's name, and needs rotation. Trusted publishing removes the credential rather than protecting it.
- **A manual `uv publish` or `twine upload` from the maintainer's machine.** It publishes a working copy rather than a tagged commit, and it keeps a token on a laptop. It stays available as the fallback if trusted publishing is ever unavailable, and using it would be a deviation from this decision rather than an alternative within it.
