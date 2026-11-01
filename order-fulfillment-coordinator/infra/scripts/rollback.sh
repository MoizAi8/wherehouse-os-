#!/usr/bin/env bash
# The previous script stopped the live service before locating any rollback image.
# This stack has no retained serving slot; do not pretend a tag is a traffic switch.
set -euo pipefail
echo 'Traffic-only rollback is unavailable in this single-stack topology.' >&2
echo 'Use recover-release.sh --check to inspect the retained release without replacing services.' >&2
echo 'Then follow docs/production-runbook.md: review database compatibility,' >&2
echo 'and obtain approval for a service replacement. No running services were changed.' >&2
exit 1
