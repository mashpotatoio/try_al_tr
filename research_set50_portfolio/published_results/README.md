# Published Phase 3 result snapshot

`20261027T162905Z_979c875c/` is the final completed Phase 3 run. It contains the frozen configuration, input hashes, full 20-session window records, daily equity, target weights, holdings, submitted/accepted/filled order records, completed FIFO lot ledger, eligibility and cost audits, uncertainty and robustness tables, and 11 figures. The executed notebook reads these files relative to this publication checkout.

The published `verification.json` records a successful reconciliation performed in the original TradeSim workspace. It checked 5,259 Phase 1 files and the original market inputs there. This publication checkout excludes raw market data and the Phase 1 integrity manifest, so that full verification cannot be repeated here. The result manifest hashes refer to the original completed run; publication copies can be checked by file hash against that workspace.

Earlier exploratory and interrupted Phase 3 result directories are omitted. The 24 evaluation windows were previously exposed in earlier research. Daily execution assumes next open with modeled one-tick adverse slippage, commission and VAT; it is not a native IOC fill record or official eligibility certificate.
