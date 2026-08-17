# Contributing

## Setup

`make setup` takes a clean checkout to a working state: it creates the environment from the lockfile and installs the pre-commit hooks. `make lint`, `make typecheck`, and `make test` run the same checks CI runs.

## Change flow

1. Every change starts as a GitHub issue stating the observable outcome. Work without an issue does not start.
2. The branch comes off current `main` and is named `<type>/<issue>-<slug>`, for example `feat/9-board`.
3. The test is written first and fails against the unmodified code.
4. The lockfile, the documentation, and the public surface land in the same commit as the change that requires them.
5. `make lint typecheck test` passes locally before the pull request opens. Local green is the precondition for opening the pull request, not a substitute for CI.
6. When `main` has moved, the branch is rebased on it. `main` is never merged into the branch.
7. The pull request title is a Conventional Commit subject; a check validates it. The body carries `Closes #<issue>`, one keyword per issue, because the squash merge discards commit messages and the body survives.
8. A pull request merges only when every check has passed, whatever the reason for a failure.
9. The merge is a squash. GitHub deletes the remote branch on merge; `git switch main && git pull --ff-only && git fetch --prune` then removes the local one.

## Review

The maintainer is sole. GitHub forbids approving one's own pull request, so no approval is requested, and a pull request merges on green CI alone. The issue link, the title check, and CI still apply to every pull request. When a second maintainer exists, required approvals replace this rule.

## Releases

release-please owns the version and `CHANGELOG.md`; neither is edited by hand. Merging a releasable commit to `main` opens or updates a release pull request, and merging that pull request cuts the release. `fix:` bumps the patch version and `feat:` bumps the minor version. While the major version is 0, a breaking change also bumps the minor version. A breaking change carries `!` in the subject and a `BREAKING CHANGE:` footer stating the migration, both together.

### What merging the release pull request does

The merge starts a chain that ends on PyPI, and no step of it is run by hand.

1. release-please writes the new version into `pyproject.toml` and `.release-please-manifest.json`, writes the changelog entries from the squashed commit subjects, tags the commit `v<version>`, and publishes a GitHub release.
2. Publishing that release triggers `.github/workflows/publish.yml`, which checks out the tagged commit.
3. The workflow compares the tag against the version the package metadata declares and stops when they disagree, so a tag can never name a version other than the one it publishes.
4. `uv build` produces the sdist and the wheel from that commit, and the workflow uploads both to PyPI.

Nothing is built or uploaded from a working copy. A maintainer who runs `uv build` locally is inspecting the artifact, not releasing it.

### Trusted publishing

The upload carries no credential. The workflow asks GitHub for an OpenID Connect token describing the repository, the workflow file, and the environment that requested it; PyPI compares that description against the publisher registered for the project and issues a credential that expires with the upload. No API token exists for this project, and none is stored in the repository, so there is nothing to leak or rotate.

The registration on PyPI, under the project's Publishing settings, is:

| Field | Value |
| --- | --- |
| PyPI project | `blackboardx` |
| Owner | `MoeinRoghani` |
| Repository | `blackboard` |
| Workflow | `publish.yml` |
| Environment | `pypi` |

The repository holds a deployment environment named `pypi`, and the workflow's `environment:` key, the environment in the repository, and the environment registered on PyPI carry the same name. A change to any one of the five values above breaks the upload until the other side matches it.

Before the project existed on PyPI these values were registered as a *pending publisher*, which is the form PyPI offers for a name that no project holds yet. The first upload created the project and converted it into an ordinary publisher on that project.

### A release that fails

Where the failure falls decides the remedy, because PyPI accepts a version once and never replaces it.

A workflow that fails before the upload, on the version check or the build, has published nothing. Correct the cause on `main` and cut the next release; re-running the job against the same tag also works when the cause was transient.

A version already on PyPI cannot be replaced, re-uploaded, or corrected in place, even after deletion. A defect in a published version is fixed by releasing the next version. A published version that must not be used is *yanked* on PyPI, which leaves it installable by exact pin for anyone who already depends on it while removing it from resolution for everyone else.
