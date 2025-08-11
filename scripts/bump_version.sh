#!/bin/bash
# Convenience script for bumping version without uv.lock conflicts
# Usage: ./scripts/bump_version.sh [patch|minor|major]

set -e

# Default to patch if no argument provided
VERSION_TYPE=${1:-patch}

# Validate version type
if [[ ! "$VERSION_TYPE" =~ ^(patch|minor|major)$ ]]; then
    echo "Error: Version type must be 'patch', 'minor', or 'major'"
    echo "Usage: $0 [patch|minor|major]"
    exit 1
fi

echo "Bumping $VERSION_TYPE version..."

# Activate virtual environment and run bump-my-version
source .venv/bin/activate
bump-my-version bump "$VERSION_TYPE"

echo "Version bump completed successfully!"
echo "Don't forget to:"
echo "1. Update CHANGELOG.md"
echo "2. git add CHANGELOG.md && git commit -m 'Update changelog for version'"
echo "3. git push origin main && git push origin --tags"
