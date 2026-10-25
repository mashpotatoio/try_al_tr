# Data quality report

The full validation command completed against **507 market CSVs**. Detailed file coverage, missing-date lists and counts are in [data_inventory.csv](experiments/20261025T155740Z_validate_dd6ea2aa/data_inventory.csv). Original inputs were not edited.

| Check | Observed result | Treatment |
|---|---|---|
| Permitted universe | 48 common shares | Use this exact list; disclose survivorship bias |
| Daily history | 49 files including SET50; 738 calendar sessions, September 21, 2023–October 6, 2026 | Strict prior-session feature cutoffs |
| Unequal histories | BANPU 45, GULF 363, MRDIYT 223, THAI 286, TIDLOR 339 rows; others 738 | Require the complete common lookback; do not backfill |
| Missing daily sessions within each symbol's observed span | None against the supplied SET50 calendar | Calendar is inferred, not independently certified |
| Tick data | 16 sessions, September 9–30, 2026; 2,906,167 rows | Native execution limited to these sessions |
| Identical tick rows | 1,046,005 repetitions beyond first occurrences | Retain; no trade IDs establish accidental duplicates |
| Tick chronology | Source files not globally chronological | Stable sort by timestamp; preserve source order for ties |
| Invalid/nonpositive prices | 0 | Invalid execution prices would stop replay |
| Invalid/negative volumes | 0 | Do not use future volume to qualify an opening fill |
| Unparseable timestamps | 0 | Interpret supplied naive exchange times as Asia/Bangkok |
| Invalid OHLC | 1 SET50 daily row | Report without repairing original values |
| Tick versus daily closing-price mismatches | 0 across all 16 sessions and 48 stocks | Raw execution remains distinct from adjusted feature history |
| Historical versus scoring SET50 close mismatches | 0 across the 16 shared dates | Keep separate source identities and period conventions |

The nine intraday intervals are available as feature history, not as extra raw tick execution days:

| Interval | Earliest observed timestamp | Latest date |
|---|---|---|
| 1 minute | 2026-09-24 09:58 | 2026-10-06 |
| 3 minutes | 2026-09-23 09:54 | 2026-10-06 |
| 5 minutes | 2026-09-21 09:55 | 2026-10-06 |
| 10 minutes | 2026-09-14 09:50 | 2026-10-06 |
| 15 minutes | 2026-09-07 09:45 | 2026-10-06 |
| 30 minutes | 2026-08-17 09:30 | 2026-10-06 |
| 60 minutes | 2026-07-01 09:00 | 2026-10-06 |
| 120 minutes | 2026-03-27 09:00 | 2026-10-06 |
| 240 minutes | 2025-09-30 09:00 | 2026-10-06 |

Coverage differs across symbols; these are earliest observations across each interval. The first or last intraday bar in a vendor file need not constitute a complete session. These research strategies use completed daily features, not intraday feature history.

## Investigated observations

**SET50, December 11, 2025:** Open 840.26, High 839.88, Low 825.54, Close 828.42. Open exceeds High, so the OHLC row is inconsistent. Its positive close lies inside Low/High and remains usable for close-only index returns; no feature in this workflow uses its invalid Open. The raw row remains unchanged.

**CCET, December 4, 2023:** Close rose from 1.51 to 1.91 (+26.4901%). Open 1.54, High 1.96 and Low 1.54 are internally consistent; volume increased from 908,064 to 129,034,104. Subsequent closes were 2.08 and 2.12. This pattern does not by itself establish erroneous data. The move is retained; no external event attribution is invented.

**MRDIYT, June 30, 2026:** Close rose from 9.35 to 12.20 (+30.4813%). Open/Low 9.35 and High/Close 12.20 are internally consistent; volume increased from 9,409,690 to 90,113,877. Subsequent closes were 10.00 and 9.85. The rounded-price move and reversal are retained. Corporate-action/event provenance is unavailable; a large percentage alone is not a deletion rule.

No returns were winsorized. The sharp September 30 decline remains in every applicable experiment.

## Unresolved provenance

The supplied history guide says prices are revised for capital actions. There are no adjustment factors, action dates, dividend cash flows, historical universe snapshots or as-published vintages. Software look-ahead tests can establish strict date cutoffs, but cannot certify that current adjusted files reproduce every historical information set. Daily execution uses those adjusted prices consistently and is labeled an approximation; native execution uses actual ticks and charges fees once.

SET50 is treated as a price index, distinct from SET50 TRI. Its local CSV name and matching overlap do not independently certify the vendor source. Missing raw execution sessions and organizer-only validation remain external blockers to official competition validation.
