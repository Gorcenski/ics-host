#!/bin/bash

PATH=$PATH:/home/ubuntu/.local/bin

# set environment variables
source .env

# download latest code
git pull --rebase

# Run your Python script
/home/ubuntu/.local/bin/uv run --project /home/ubuntu/ics-host src/compile.py