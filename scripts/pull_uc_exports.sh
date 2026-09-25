#!/usr/bin/env bash
# Pull position-hub exports from the Unity Catalog Volume to a local machine with the Databricks CLI.
# Browser OAuth; no token typed or stored here. Run the notebook in the workspace first.
set -euo pipefail
HOST="${DATABRICKS_HOST:-https://adb-7405617646104787.7.azuredatabricks.net}"
REMOTE="${POSHUB_UC_VOLUME:-/Volumes/pff/bronze/exports}/position_hub"
LOCAL="${PANTHERS_DATA_DIR:-$HOME/panthers_projects}/data/position_hub"
command -v databricks >/dev/null || { echo "install the Databricks CLI (brew tap databricks/tap && brew install databricks)"; exit 1; }
databricks auth login --host "$HOST"
databricks current-user me
databricks fs ls "dbfs:$REMOTE" || { echo "nothing at $REMOTE — run notebooks/databricks/01_role_snaps_uc.py first"; exit 1; }
mkdir -p "$LOCAL"
databricks fs cp -r "dbfs:$REMOTE" "$LOCAL" --overwrite
du -sh "$LOCAL"
