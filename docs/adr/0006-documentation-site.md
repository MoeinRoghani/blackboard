# ADR 0006: The documentation site

Date: 2026-08-17

## Status

Accepted

## Context

The repository is private, so the README, the contributing guide, and the decision records reach nobody outside it, while the distribution on PyPI is public. Documentation that can be read without repository access is therefore needed, and the library's public surface of 57 names is large enough that a hand-written reference would drift from the docstrings.

Three generators were considered. Docusaurus is a React application. Sphinx is the traditional Python generator. MkDocs with the Material theme renders Markdown and, through mkdocstrings, reads the docstrings in the package.

## Decision

The site is built by MkDocs with the Material theme and mkdocstrings, configured in `mkdocs.yml`, and `make docs` builds it. The pages include the committed documents through snippets rather than copying them, so the README and the contributing guide have one source each, and the API reference is generated from the docstrings.

`mkdocs` is constrained to `<2`. Its maintainers have announced that version 2.0 removes the plugin system, rewrites theming, offers no migration path, and is currently unlicensed.

A CI job runs `mkdocs build --strict`, so a broken link or a reference to a deleted symbol fails the build before merge, which is what the coding standard requires of a documentation build.

## Consequences

- A public name without a docstring is visible as a gap in the reference. Writing this configuration exposed six type aliases carrying no documentation, and they were documented rather than hidden.
- The documentation toolchain installs from the same lockfile as the tests, and Dependabot updates it like any other dependency.
- Nothing about the generator decides where the site is served. The build produces static files, which any host serves.

## Alternatives rejected

- **Docusaurus.** It would add a Node toolchain, a second manifest, and a second lockfile to a repository that holds one Python package at its root, and it cannot read Python docstrings, so the API reference would be written by hand and would drift.
- **Sphinx.** It reads docstrings as well, and its reStructuredText default does not match documents already written in Markdown; adopting it would mean either converting them or configuring MyST to read what MkDocs reads natively.
- **A hand-written reference.** The surface is 57 names whose docstrings are already reviewed against the writing standards; a second copy would restate them and fall behind.
