# Databricks connection — setup and the probe ladder

Workspace: `https://adb-7405617646104787.7.azuredatabricks.net` (Azure Databricks, `o=7405617646104787`).
Everything PFF is under `pff.bronze`. `poshub probe` walks six rungs and names the remedy for the first
one that fails; run it before anything else.

```
$ poshub probe
databricks probe · https://adb-7405617646104787.7.azuredatabricks.net
  [OK ] host      HTTP 401
  [OK ] auth      achappidi@panthers.nfl.com (Akhi)
  [OK ] catalog   pff schemas: bronze, cff, cfl, ufl, silver, gold
  [OK ] warehouse auto-picked Serverless Starter Warehouse [RUNNING] /sql/1.0/warehouses/…
  [OK ] sql       SELECT 1 via Statement Execution API on warehouse …
  [OK ] table:pffplays          pff.bronze.pffplays: 1,019,359 rows, 303 cols
  [OK ] table:pffdefense        pff.bronze.pffdefense: 9,184,293 rows, 56 cols
  [OK ] table:coverage_defense  pff.bronze.coverage_defense: 1,205,631 rows, 45 cols
```
(illustrative output; the numbers come from the sister project's last measurement)

## Three ways to authenticate — pick one

| where you run | credential | env |
|---|---|---|
| your laptop (the PanthersScout way) | **Azure CLI**: `az login` once; the client asks `az account get-access-token --resource 2ff814a6-3304-4ab8-85cb-cd0e6f879c1d` on every call | `DATABRICKS_HOST` only |
| your laptop, no Azure CLI | OAuth, browser login: `pip install databricks-sdk && databricks auth login --host <workspace>` | `DATABRICKS_HOST`, optional `DATABRICKS_CONFIG_PROFILE` |
| a headless box, a Claude cloud session | personal access token (User settings → Developer → Access tokens → Generate) | `DATABRICKS_HOST`, `DATABRICKS_TOKEN` |
| a service, CI | Azure service principal added to the workspace (Admin → Identity → Service principals) | `DATABRICKS_HOST`, `ARM_TENANT_ID`, `ARM_CLIENT_ID`, `ARM_CLIENT_SECRET` |

The client tries them in the order PAT → service principal → Azure CLI → SDK chain. The service-principal path is pure
`requests` against `login.microsoftonline.com` for the fixed Azure Databricks resource id
`2ff814a6-3304-4ab8-85cb-cd0e6f879c1d`; no CLI needed.

`DATABRICKS_HTTP_PATH` (SQL Warehouses → the warehouse → Connection details → HTTP path) is optional: when it
is unset the client lists the warehouses this identity can use and takes the running one, printing which.

## In a Claude cloud session (this environment)
Two settings, both under the environment menu in the session title bar → Edit:

1. **Network access.** The policy denied the workspace host (measured: `CONNECT tunnel failed, response 403`
   on `adb-7405617646104787.7.azuredatabricks.net:443`). Either broaden the access level or add these to the
   allowed domains:
   - `adb-7405617646104787.7.azuredatabricks.net` — the workspace (REST, SQL Statement API)
   - `login.microsoftonline.com` — only for the service-principal path (already reachable here)
   - the storage account behind large SQL results, if you want multi-million-row pulls in-session: the
     Statement API hands back presigned `*.blob.core.windows.net` / `*.dfs.core.windows.net` links for
     results above the inline limit. Small queries (`LIMIT ≤ 50,000`) use INLINE and need only the workspace host.
2. **Secrets / environment variables.** `DATABRICKS_HOST`, `DATABRICKS_TOKEN` (or the three `ARM_*`), and
   `DATABRICKS_HTTP_PATH` if you want a specific warehouse. A new session picks them up; never paste a token
   into chat.

Then `poshub probe`, then `poshub discover`, then the pipeline.

## What each rung failing means
| rung | fails when | fix |
|---|---|---|
| host | network policy, DNS, proxy | allow the host; or run the notebook in the workspace |
| auth | no credential, expired PAT, SP not in workspace | regenerate PAT / add SP / `databricks auth login` |
| catalog | identity lacks `USE CATALOG pff` / `USE SCHEMA pff.bronze` | ask the workspace admin |
| warehouse | none visible, or `DATABRICKS_HTTP_PATH` names one you cannot use | `CAN USE` on a warehouse |
| sql | warehouse stopped and cannot start, Statement API disabled | start it; check workspace settings |
| table:* | `SELECT` missing, or the table names differ from the contract | grants; `poshub discover` then fix `pff/loaders.py` |

## Big pulls
`poshub features` reads `pffplays` for the seasons asked (~50k rows/season), then `pffdefense` in chunks of
400 games and `coverage_defense` per season. Those go through EXTERNAL_LINKS (Arrow). With
`databricks-sql-connector` installed the same calls stream Arrow directly and skip the presigned links.
Alternatively run `notebooks/databricks/01_role_snaps_uc.py` in the workspace and pull one parquet folder
with `scripts/pull_uc_exports.sh`.
