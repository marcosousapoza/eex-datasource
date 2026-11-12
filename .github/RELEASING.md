# Releasing to PyPI

Releases are built in GitHub Actions and published with PyPI Trusted Publishing. Do not upload
local `dist/` files or create a long-lived PyPI API token.

## One-time project setup

1. Push this repository to GitHub and make `main` the default branch.
2. Create a GitHub environment named `pypi`. Add required reviewers if release approval is desired.
3. On PyPI, create a pending Trusted Publisher for distribution `eex-datasource` with:
   - GitHub owner: the repository owner or organization;
   - repository: the GitHub repository name;
   - workflow: `publish.yml`;
   - environment: `pypi`.
4. Protect `main` and require the `CI` workflow before merging.

The package name currently appears unclaimed, but PyPI determines availability when the pending
publisher or first project release is created.

## Release procedure

1. Update `project.version` in `pyproject.toml` and summarize notable changes in the GitHub Release.
2. Merge the release changes after CI passes.
3. Create a GitHub Release with tag `v<project.version>`, for example `v0.1.0`.
4. Publish the GitHub Release.
5. Approve the `pypi` environment deployment if approval is configured.
6. Confirm the release at <https://pypi.org/project/eex-datasource/> and test installation in a clean
   environment.

The workflow rejects a release when the Git tag and `pyproject.toml` version differ. It validates
the wheel and source distribution with Twine before the publish job receives an OIDC identity.
