#!/usr/bin/env bash
# Regenerates the extraction Lambda layer content from the single canonical
# sources at backend/core/{care_event,extraction,persistence}/. Run this
# before `aws cloudformation package` / `aws cloudformation deploy` so the
# layer ContentUri directory reflects current source instead of a
# hand-copied, easily-stale duplicate. Mirrors build_layer.sh's approach for
# the Day 1 transcription layer.
#
# Unlike the transcription layer, these three packages import each other
# via absolute `backend.core.X` imports (not relative imports), so the
# layer preserves that same package path - backend/core/{care_event,
# extraction,persistence} - rather than flattening to a bare `core.*`
# namespace the way the transcription layer does. The extraction Lambda's
# handler.py imports `from backend.core.care_event import ...` etc, exactly
# as the test suite does.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAYER_PYTHON_DIR="$REPO_ROOT/backend/layers/extraction/python"
DEST_ROOT="$LAYER_PYTHON_DIR/backend/core"

rm -rf "$LAYER_PYTHON_DIR"
mkdir -p "$DEST_ROOT"

for pkg in care_event extraction persistence; do
  SOURCE_DIR="$REPO_ROOT/backend/core/$pkg"
  DEST_DIR="$DEST_ROOT/$pkg"
  mkdir -p "$DEST_DIR"
  cp "$SOURCE_DIR"/*.py "$DEST_DIR"/
done

echo "Layer content regenerated at $LAYER_PYTHON_DIR"
