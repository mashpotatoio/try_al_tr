# Phase 3.5 execution validation

Run from the repository root:

```powershell
python -m research_set50_execution_validation.run
python -m research_set50_execution_validation.native_check research_set50_execution_validation/results/<experiment_id>
python -m research_set50_execution_validation.report research_set50_execution_validation/results/<experiment_id>
python -m research_set50_execution_validation.build_notebook research_set50_execution_validation/results/<experiment_id>
python -m unittest discover research_set50_execution_validation/tests
```

Outputs are written to a new timestamped `results/` folder. The frozen Phase 3 code, config, and results are read only. All 24 historical evaluation windows were previously examined; variants are exploratory. `report` builds and executes a 24-cell analytical notebook and exports a self-contained HTML copy to `publication/phase35_execution_diagnostics.html`. The separate `build_notebook` command regenerates those publication artifacts from an existing result folder without rerunning the experiments.
