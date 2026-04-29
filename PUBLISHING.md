# Publishing

Releases are automated by [.github/workflows/publish.yml](.github/workflows/publish.yml). Bumping `spytial/_version.py` on `main` is the release action.

## Normal release flow

1. Bump the version in `spytial/_version.py`.
2. Commit and push to `main` (directly, or via merged PR).
3. The publish workflow runs automatically and:
   - reads the new version,
   - skips if that version already exists on PyPI,
   - runs the test suite,
   - builds sdist + wheel with `python -m build`,
   - uploads to PyPI,
   - creates the git tag `vX.Y.Z` and a GitHub Release with auto-generated notes.

Watch progress under the repo's **Actions** tab. The workflow can also be triggered manually via **Run workflow** (`workflow_dispatch`) on the same `main` commit — useful for retrying a failed publish without making a no-op commit.

## First-time setup (one-time)

The workflow needs a PyPI API token stored as a repo secret.

1. Create a project-scoped token at https://pypi.org/manage/account/token/ (scope: project `spytial-diagramming`).
2. In the GitHub repo, go to **Settings → Secrets and variables → Actions → New repository secret** and add:
   - Name: `PYPI_API_TOKEN`
   - Value: the `pypi-...` token string.

Without this secret the `publish` job will fail; everything else (detect/test/build) will still run.

## Manual fallback (emergency only)

If GitHub Actions is unavailable, the manual flow still works:

```bash
rm -rf dist/ build/ *.egg-info/
python -m pip install --upgrade build twine
python -m build --no-isolation
python -m pytest test/ -q
export TWINE_USERNAME="__token__"
export TWINE_PASSWORD="pypi-<PROD_API_TOKEN>"
python -m twine upload dist/*
```

After a manual publish, push a `vX.Y.Z` tag so the release history stays consistent with the automated flow:

```bash
git tag vX.Y.Z && git push origin vX.Y.Z
```

## Troubleshooting

- **`detect` job runs but everything else is skipped.** The version in `spytial/_version.py` already exists on PyPI. Bump it.
- **`publish` fails with 403.** Either `PYPI_API_TOKEN` is missing/expired, or the token's scope doesn't include `spytial-diagramming`. Regenerate a project-scoped token and update the secret.
- **`publish` fails with "File already exists".** Someone published this version out of band (probably via the manual fallback). Bump the version again.
- **`release` fails to create a tag.** The `vX.Y.Z` tag already exists on the commit. Delete the stale tag (`git push --delete origin vX.Y.Z`) or bump the version.
