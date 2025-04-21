#!/bin/bash
# set environment variables
source .env

# download latest code
git pull --rebase

# Activate the virtual environment
source .venv/bin/activate

# Run your Python script
uv run src/compile.py