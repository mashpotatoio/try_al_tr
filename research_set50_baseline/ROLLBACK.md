# Recovery without deleting unrelated work

No original source, notebook, data, environment, or prior result file was changed. No Git repository existed, so no branch or commit was created. Research changes live exclusively under `research_set50_baseline/`. `original_manifest.json` records SHA-256 hashes for 539 original files; each experiment also contains a source snapshot and data manifest. Source ZIP checkpoints exclude market data, environments, vendored plotting packages, and experiment results.

## Run the original project

```powershell
Set-Location 'C:\Users\Windows 10\Downloads\tradeSim0.2.5'
& '.\tradeSimEnv\Scripts\python.exe' -m jupyter notebook '.\TradingSimulation.ipynb'
```

The original notebook's `fresh_start=True` cell deletes the chosen team's existing `result/<team_name>` directory. Before running that cell, use a **new unique** `team_name` such as `original_review_20261025a` in the interactive session, leave `strategy_name = 'Example_strategy'`, and confirm that result directory does not already exist. Do not save notebook edits if you want the source notebook byte-for-byte unchanged. To continue the existing example portfolio intentionally, use `fresh_start=False` instead; that changes its saved results. This research task did not execute those notebook cells.

## Inspect original-file integrity

```powershell
$root = (Resolve-Path '.').Path
$baseline = Get-Content -LiteralPath '.\research_set50_baseline\original_manifest.json' -Raw | ConvertFrom-Json
$changed = foreach ($entry in $baseline.PSObject.Properties) {
    $file = Join-Path $root $entry.Name
    if (-not (Test-Path -LiteralPath $file)) {
        $entry.Name
    } elseif ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value) {
        $entry.Name
    }
}
$changed
Get-ChildItem -LiteralPath '.\research_set50_baseline' -Force
```

An empty `$changed` list means all recorded original files still match. Inspect `experiments/*/status.json`, configurations and manifests to see successful and failed attempts. The failed first smoke report is retained; its simulations completed, but plotting was then unavailable.

## Disable or roll back this task while preserving all results

Close research processes first. This moves only the validated task directory to a unique sibling archive:

```powershell
$root = (Resolve-Path '.').Path
$taskPath = (Resolve-Path -LiteralPath '.\research_set50_baseline').Path
$expected = Join-Path $root 'research_set50_baseline'
if ($taskPath -ne $expected) { throw 'Unexpected task path; stop.' }
$archiveName = 'research_set50_archive_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '_' + [guid]::NewGuid().ToString('N').Substring(0,8)
$archivePath = Join-Path $root $archiveName
if (Test-Path -LiteralPath $archivePath) { throw 'Archive already exists; stop.' }
Move-Item -LiteralPath $taskPath -Destination $archivePath
```

The original project remains runnable. This operation preserves experiments, checkpoints, docs and plotting packages inside the archive. No reset, clean, recursive deletion, or parent-directory Git initialization is needed.

## Restore a source checkpoint without destroying later work

After archiving as above, choose the exact ZIP from the archive's `checkpoints/` directory:

```powershell
Get-ChildItem -LiteralPath (Join-Path $archivePath 'checkpoints') -Filter '*.zip'
$checkpoint = '<absolute path to the chosen checkpoint ZIP>'
$restorePath = Join-Path $root 'research_set50_baseline'
if (Test-Path -LiteralPath $restorePath) { throw 'Restore destination exists; archive it first.' }
Expand-Archive -LiteralPath $checkpoint -DestinationPath $restorePath
& '.\tradeSimEnv\Scripts\python.exe' -X utf8 -B -m research_set50_baseline.bootstrap_plotting
```

The archived later experiments remain untouched. A per-experiment source snapshot is also available under `experiments/<id>/source/`; pair it with that experiment's `config.json` and original data hashes. Do not replace original engine/data files if their current hashes differ: locate the corresponding original distribution separately instead.

## Start another fresh experiment

```powershell
& '.\tradeSimEnv\Scripts\python.exe' -X utf8 -B -m research_set50_baseline run-native
```

Every invocation creates a new directory and fresh subprocesses. There is no resume or overwrite mode. Failed run folders remain inspectable. Rebuilding a report creates a new report directory when one already exists.
