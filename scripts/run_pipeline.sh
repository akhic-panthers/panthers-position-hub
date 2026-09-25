#!/usr/bin/env bash
# features → fit → score → mix, for the seasons given (default 2024 2025). Needs tracking under PANTHERS_DATA_DIR.
set -euo pipefail
SEASONS="${*:-2024 2025}"
poshub status --offline
poshub features --seasons $SEASONS
poshub fit --holdout-weeks 17 18
poshub score
poshub mix
cat out/gates.md
