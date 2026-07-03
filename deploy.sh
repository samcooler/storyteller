#!/bin/sh
# Push current branch to the Pi's bare repo and pull it into the working copy there.
set -e

BRANCH=$(git rev-parse --abbrev-ref HEAD)

echo "Pushing $BRANCH to pi..."
git push pi "$BRANCH"

echo "Pulling on storyteller-pi..."
ssh storyteller-pi "cd ~/storyteller && git pull"

echo "Done. SSH in and run: cd ~/storyteller && python3 main.py --fullscreen"
