#!/bin/bash
# Regenerate the published .ics feeds from the Baikal `default` calendar.
#
# Deployment is pull-based: this updates itself from git before running, so
# pushing to main is the deploy. Invoked by /etc/cron.d/ics-publish.
set -euo pipefail

cd "$(dirname "$0")"

# publish.py loads .env itself via python-dotenv, so no `source .env` here —
# that would also export the Baikal password into the environment of anything
# else this script ran.

# Fast-forward only, not --rebase. Rebasing onto a dirty checkout can silently
# run code that was never pushed or reviewed; if the working copy has diverged,
# say so and keep running the last known-good version.
git fetch --quiet origin main || echo "$(date -Is) git fetch failed — running existing code" >&2
git merge --ff-only --quiet origin/main || echo "$(date -Is) checkout diverged from origin/main — running existing code" >&2

# Dependencies live in a local venv; the host has no uv installed.
exec ./.venv/bin/python src/publish.py
