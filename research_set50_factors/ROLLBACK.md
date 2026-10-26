# Safe rollback and recovery

The original engine, daily and tick data, Phase 1 source, tests, and results were left in place. `phase1_prephase2_sha256.json` records pre-Phase-2 file hashes; each Phase 2 run records source and market-data hashes. The baseline research checkpoint is commit `ac2ab82c6507b7ea6249f4f7c14a2004debdf9d9` in the separate Git metadata directory `.phase2_git_meta`. The `research/phase2-factors` branch holds Phase 2 source. A pre-existing nested repository in `try_al_tr_phase1_publication/` remains separate.

The filesystem sandbox prevented writes to the root `.git` directory during initialization. It contains an incomplete Git stub and was not used for commits. Always pass `--git-dir=.phase2_git_meta --work-tree=.` for this checkpoint. Do not run `git clean`, `git reset --hard`, or recursive deletion against the workspace.

To verify Phase 1 integrity from the workspace root:

```powershell
& '.\tradeSimEnv\Scripts\python.exe' -X utf8 -B -c "from research_set50_factors.data import verify_phase1_manifest; print(verify_phase1_manifest())"
git --git-dir=.phase2_git_meta --work-tree=. status --short --branch
```

To archive only Phase 2, first stop running research processes, then check the resolved paths and move the directory to a unique sibling name:

```powershell
$root = (Resolve-Path '.').Path
$source = (Resolve-Path -LiteralPath '.\research_set50_factors').Path
$expected = Join-Path $root 'research_set50_factors'
if ($source -ne $expected) { throw 'Unexpected source path' }
$destination = Join-Path $root ('research_set50_factors_archive_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '_' + [guid]::NewGuid().ToString('N').Substring(0,8))
if (Test-Path -LiteralPath $destination) { throw 'Archive already exists' }
Move-Item -LiteralPath $source -Destination $destination
```

This preserves all runs and the executed notebook. To restore it, move that exact archive back only after confirming `research_set50_factors` is absent. Leave `.phase2_git_meta`, the incomplete root `.git` stub, and the nested publication repository untouched unless their state has been independently reviewed. Phase 1 runs remain in their original directories throughout.
