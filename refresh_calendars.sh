#!/bin/bash
# download latest code
git checkout

# Activate the virtual environment
source .venv/bin/activate

# Run your Python script
uv src/compile.py