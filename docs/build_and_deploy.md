# Building and Deploying

This project ships with a GitHub Actions workflow for publishing releases to PyPI. Pushing a tag that starts with `v` (for example `v0.2.0`) triggers the workflow defined in `.github/workflows/publish.yml`. The workflow builds the package and uploads it using the `PYPI_API_TOKEN` secret from the repository settings.

For manual publishing or local testing the helper script `scripts/publish_pypi.sh` is still available. It performs the build and calls `twine upload` on the resulting files in the `dist/` directory. Set the `TWINE_PASSWORD` environment variable to your API token before running the script.

## Versioning

Versions are defined in both `pyproject.toml` and `aicostmanager/__init__.py`. The project uses [bump-my-version](https://github.com/callowayproject/bump-my-version) to update these files consistently and create a git tag:

```bash
uv pip install -e .[dev]  # or `pip install -e .[dev]`

bump-my-version bump patch  # bump patch/minor/major
```

After bumping the version a commit and tag are created. Update `CHANGELOG.md` with a summary of changes and push the tag to trigger the GitHub workflow and publish the release automatically.

## Manual build and publish

Run the build step if you want to test the package locally:

```bash
python -m build
```

This will generate the `dist/` archives. To upload them manually run:

```bash
./scripts/publish_pypi.sh
```

Twine will upload the contents of `dist/` to PyPI. Verify the release on the PyPI project page afterwards.
