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
