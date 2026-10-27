# Trading cost decomposition

The same frozen decisions and 24 evaluation windows were rerun for every A scenario. Price changes alter affordable shares and later holdings, so scenario differences are path effects as well as paid fees. Gross-return proxy in Phase 3 adds booked costs to final NAV but is **not** a separate no-cost portfolio path. Saved Phase 3 costs for all A–E are:

| strategy | gross_return_proxy | mean_net | mean_excess | mean_turnover | commission_thb | vat_thb | slippage_thb | total_explicit_cost_thb |
|---|---|---|---|---|---|---|---|---|
| A | 0.01945 | -0.00171 | -0.00899 | 2.79395 | 43935.42217 | 3075.47955 | 164589.58333 | 211600.48506 |
| B | 0.01732 | -0.00495 | -0.01223 | 2.9861 | 46950.93269 | 3286.56529 | 172416.83333 | 222654.33131 |
| C | 0.0183 | -0.00301 | -0.0103 | 2.84067 | 44669.7868 | 3126.88508 | 165395.04167 | 213191.71354 |
| D | 0.01572 | -0.00706 | -0.01434 | 3.08728 | 48539.77347 | 3397.78414 | 175832.875 | 227770.43261 |
| E | 0.01933 | 0.00454 | -0.00275 | 1.92575 | 30301.72174 | 2121.12052 | 115492.29167 | 147915.13393 |

| experiment | mean_excess | mean_turnover | mean_commission | mean_vat | mean_slippage | mean_cost_pct | mean_roundtrips | common_pass | best_alpha_pass |
|---|---|---|---|---|---|---|---|---|---|
| commission | 0.00779 | 2.80575 | 44050.30679 | 0.0 | 0.0 | 0.00441 | 9.20833 | 3 | 2 |
| commission_vat | 0.00748 | 2.80566 | 44048.85219 | 3083.41965 | 0.0 | 0.00471 | 9.20833 | 3 | 2 |
| half_fills | -0.00808 | 1.48906 | 23445.22899 | 1641.16603 | 88023.75 | 0.01131 | 1.25 | 0 | 0 |
| one_tick | -0.00899 | 2.79395 | 43935.42217 | 3075.47955 | 164589.58333 | 0.02116 | 9.0 | 2 | 2 |
| positive_momentum | -0.00896 | 2.79674 | 43979.21091 | 3078.54476 | 165192.33333 | 0.02123 | 9.0 | 2 | 2 |
| rebalance_every_10 | 0.00106 | 1.58395 | 24936.88658 | 1745.58206 | 93575.66667 | 0.01203 | 3.0 | 0 | 0 |
| two_ticks | -0.02536 | 2.78386 | 43845.64035 | 3069.19482 | 327989.41667 | 0.03749 | 8.91667 | 0 | 0 |
| unconstrained_cap | -0.00873 | 2.83989 | 44657.40649 | 3126.01845 | 167280.625 | 0.02151 | 9.125 | 2 | 2 |
| zero | 0.0122 | 2.80867 | 0.0 | 0.0 | 0.0 | 0.0 | 9.16667 | 5 | 3 |

For A, no-cost mean excess is 1.2199%; one-tick net mean excess is -0.8990%. The gap is 2.1189% of initial capital. Mean booked commission is THB 43,935.42, VAT THB 3,075.48, adverse-tick impact THB 164,589.58, jointly 2.1160% of initial capital. The residual 0.0029% is execution-path/sizing difference at mean level, including changed cash and holdings. It is not a separately charged fee. Commission-only leaves 0.7792% mean excess; commission plus VAT leaves 0.7484%. Two adverse ticks give -2.5364%. Removing only the 1% prior-volume cap gives -0.8734%; half fills give -0.8076%. These are sensitivity bounds, not verified IOC outcomes.

At turnover 2.794× initial capital, the booked cost hurdle is 2.116%. An approximate per-notional cost is 0.757%; at turnover 1×, 2×, and 3× initial capital, corresponding break-even gross alpha is about 0.757%, 1.515%, and 2.272%. This linear approximation holds execution mix fixed. The apparent pre-cost 1.22% mean excess is smaller than the 2.12% booked hurdle and is not proof of a predictive signal. Adjusted-open tick slippage could overstate or understate real spread/impact; quote depth, latency and historical raw prices are missing.
