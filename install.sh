#!/usr/bin/env bash
# Install Tide: copies tide.py to ~/.tide, adds the Notification hook, schedules the flush.
set -euo pipefail

if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "Tide needs Python 3.11 or newer." >&2
  exit 1
fi

cd "$(dirname "$0")"
python3 tide.py install
