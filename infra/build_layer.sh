#!/usr/bin/env bash
# Regenerates the transcription Lambda layer content from the single
# canonical source at backend/core/transcription/. Run this before
# `aws cloudformation package` / `aws cloudformation deploy` so the layer
# ContentUri directory reflects the current source instead of a hand-copied,
# easily-stale duplicate.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="$REPO_ROOT/backend/core/transcription"
LAYER_PYTHON_DIR="$REPO_ROOT/backend/layers/transcription/python"
DEST_DIR="$LAYER_PYTHON_DIR/core/transcription"

rm -rf "$LAYER_PYTHON_DIR"
mkdir -p "$DEST_DIR"
cp "$SOURCE_DIR"/*.py "$DEST_DIR"/

echo "Layer content regenerated at $DEST_DIR"
