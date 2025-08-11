# Building and Deploying

This document provides a complete step-by-step guide for releasing new versions of the AICostManager Python SDK. The process is largely automated via GitHub Actions, but requires some manual steps for version management and changelog updates.

## Prerequisites

Before you begin, ensure you have:

1. **Development dependencies installed:**
   ```bash
   uv pip install -e .[dev]
   ```
   This installs: `build`, `twine`, and `bump-my-version`

2. **Repository access:** Push access to the main branch and ability to create tags

3. **GitHub secrets configured:** The repository should have `PYPI_API_TOKEN` secret set for automated PyPI publishing

## Step-by-Step Release Process

### Step 1: Prepare Your Changes

1. **Ensure all changes are committed and pushed to main:**
   ```bash
   git status  # Should show clean working directory
   git push origin main
   ```

2. **Run tests to ensure everything works:**
   ```bash
   pytest  # Run the full test suite
   ```

### Step 2: Bump the Version

The project uses [bump-my-version](https://github.com/callowayproject/bump-my-version) to automatically update version numbers in both `pyproject.toml` and `aicostmanager/__init__.py`.

**Choose the appropriate version bump:**
- `patch` - for bug fixes (0.1.12 → 0.1.13)
- `minor` - for new features (0.1.12 → 0.2.0)  
- `major` - for breaking changes (0.1.12 → 1.0.0)

```bash
# RECOMMENDED: Use the convenience script to avoid uv.lock conflicts
./scripts/bump_version.sh patch    # for patch releases (most common)
./scripts/bump_version.sh minor    # for minor releases  
./scripts/bump_version.sh major    # for major releases

# OR: Use direct command (requires activated virtual environment)
source .venv/bin/activate
bump-my-version bump patch

# AVOID: Don't use 'uv run' as it can modify uv.lock before checking clean status
# uv run bump-my-version bump patch  # ❌ This causes the uv.lock issue
```

**What this does:**
- Updates version in `pyproject.toml` (line 7)
- Updates version in `aicostmanager/__init__.py` (line 3)
- Creates a git commit with the version changes
- Creates a git tag (e.g., `v0.1.13`)

### Step 3: Update the Changelog

1. **Edit `CHANGELOG.md`** to document the changes for this release:
   ```bash
   # Edit the file to add a new section at the top
   vim CHANGELOG.md  # or use your preferred editor
   ```

2. **Follow the existing format:**
   ```markdown
   ## [0.1.13] - 2025-01-XX
   ### Added
   - New feature descriptions
   
   ### Fixed
   - Bug fix descriptions
   
   ### Changed
   - Breaking change descriptions
   ```

3. **Commit the changelog update:**
   ```bash
   git add CHANGELOG.md
   git commit -m "Update changelog for v0.1.13"
   ```

### Step 4: Push and Trigger Automated Deployment

1. **Push the version commit and tag:**
   ```bash
   git push origin main
   git push origin --tags
   ```

   **Important:** Pushing the tag (which starts with `v`) automatically triggers the GitHub Actions workflow.

2. **Monitor the GitHub Actions workflow:**
   - Go to the "Actions" tab in your GitHub repository
   - Watch the "Publish package to PyPI" workflow run
   - The workflow will:
     - Checkout the code
     - Set up Python 3.11
     - Install build tools
     - Build the package with `python -m build`
     - Publish to PyPI using the `PYPI_API_TOKEN` secret

### Step 5: Verify the Release

1. **Check GitHub Actions completed successfully:**
   - Ensure the workflow shows a green checkmark
   - Review any errors if the workflow fails

2. **Verify on PyPI:**
   - Visit [https://pypi.org/project/aicostmanager/](https://pypi.org/project/aicostmanager/)
   - Confirm the new version is listed
   - Check that the package description and metadata look correct

3. **Test the published package:**
   ```bash
   # In a fresh virtual environment (uv)
   uv pip install aicostmanager==0.1.14  # Use your new version
   python -c "import aicostmanager; print(aicostmanager.__version__)"
   ```

## Manual Build and Publish (Backup Method)

If the GitHub Actions workflow fails or you need to publish manually:

### Local Build Testing

```bash
# Clean any previous builds
rm -rf dist/ build/

# Build the package
python -m build
```

This generates files in the `dist/` directory:
- `.tar.gz` source distribution
- `.whl` wheel distribution

### Manual PyPI Upload

```bash
# Set your PyPI API token
export TWINE_PASSWORD="your-pypi-api-token"

# Use the publish script
./scripts/publish_pypi.sh
```

Or manually with twine:
```bash
twine upload dist/*
```

## Troubleshooting

**Common issues and solutions:**

1. **Version bump fails:** Ensure you're on the main branch with a clean working directory
2. **GitHub Actions fails:** Check that `PYPI_API_TOKEN` secret is set in repository settings
3. **PyPI upload rejected:** Version might already exist (PyPI doesn't allow overwriting)
4. **Import errors after install:** Verify package contents with `uv pip show -f aicostmanager` (or `pip show -f aicostmanager`)

## Quick Reference Commands

```bash
# Complete release process:
git status && git push origin main
./scripts/bump_version.sh patch
# Edit CHANGELOG.md
git add CHANGELOG.md && git commit -m "Update changelog for vX.X.X"
git push origin main && git push origin --tags

# Manual build:
python -m build

# Manual publish:
./scripts/publish_pypi.sh
```
