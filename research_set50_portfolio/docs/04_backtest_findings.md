# Phase 3 findings

Run: `20261027T162905Z_979c875c`. Development selected E base: **A**. All evaluation dates were previously exposed in prior research. The final verifier passed: 356 window records across base, development, stress and exit scenarios; 7,120 daily equity records; 9,915 submitted orders; 2,463 completed FIFO lots; and 11 figures. The executed notebook has six code cells. Seven current unit and integration tests pass.

## Evaluation (24 windows)

```text
           mean_net  median_net  worst_net  mean_excess  common_pass  best_alpha_pass  mean_turnover  mean_roundtrips
strategy                                                                                                             
A           -0.0017     -0.0169    -0.0868      -0.0090       0.0833           0.0833         2.7940           9.0000
B           -0.0049     -0.0153    -0.0837      -0.0122       0.1250           0.1250         2.9861           9.2917
C           -0.0030     -0.0163    -0.0891      -0.0103       0.1250           0.0833         2.8407           9.0833
D           -0.0071     -0.0208    -0.0881      -0.0143       0.1667           0.1250         3.0873           8.9583
E            0.0045     -0.0089    -0.0851      -0.0027       0.0000           0.0000         1.9257           4.6250
buy_hold    -0.0024     -0.0012    -0.0700      -0.0097       0.0000           0.0000         0.7850           0.0000
risk_only   -0.0016     -0.0156    -0.0813      -0.0089       0.0833           0.0833         2.6249           9.0417
sma_trend   -0.0000     -0.0068    -0.0688      -0.0073       0.0833           0.0417         1.7730           4.7917
```

## Interpretation

The reversal tie-breaker does not establish a net edge: compare C with A and D with B under identical scheduled execution. E reduces turnover, but its lower natural FIFO lot completion can fail the five-round-trip gate. A positive average net return alone does not establish robust excess return.

The base A strategy has mean net return **−0.17%**, mean net excess **−0.90%**, median excess **−2.77%**, and Best Alpha eligibility **2/24** windows. The reversal/equal C control has mean net excess **−1.03%** and also **2/24** eligible; inverse-volatility B and D each have **3/24** eligible but worse mean excess (**−1.22%** and **−1.43%**). This does not support an incremental reversal or inverse-volatility advantage. The 24-window bootstrap interval for A mean excess is **−3.05% to +1.40%**, crossing zero. This is a variability interval on reused historical windows, not an untouched test.

E's mean net return is **+0.45%**, but median net return is **−0.89%**, mean excess is **−0.27%**, and Best Alpha eligibility is **0/24**. Average exposure remains **75.35%**. Average FIFO completions fall to **4.63**; only **13/24** windows meet the five-completion count, and only **3/24** pass expected payoff. Mean turnover falls from A's **2.79×** initial capital to **1.93×**. The separate risk-only control has mean excess **−0.89%** and **2/24** eligibility, so reduced target exposure and tighter caps alone do not establish an improvement.

The no-cost A diagnostic has mean excess **+1.22%**. Under official estimated costs it is **−0.90%**, and with two adverse ticks **−2.54%**; the half-fill scenario has **0/24** eligibility. Mean A window cost attribution is about **THB 43,935 commission**, **THB 3,075 VAT**, and **THB 164,590 modeled slippage**. These comparisons show substantial sensitivity to the raw-tick assumption on adjusted historical prices. The exploratory rank-retention exit reduces turnover to **2.10×** and improves A mean excess to **−0.32%**, but eligibility falls to **1/24**. It was inspected on exposed dates and is not a newly confirmed edge.

Ex-post market-regime diagnostics split windows into six down, nine sideways, and nine up periods using each completed window's benchmark return. A's mean excess is about **+0.42%** down, **+0.48%** sideways, and **−3.16%** up. This is descriptive: the regime is not known at entry and cannot be used as a trading filter without a separate point-in-time test.

Modeled one-tick cost is a sensitivity assumption applied to vendor-revised adjusted opens. It is not validated executable historical pricing. Large modeled slippage makes this limitation material. Participation caps and half-fill scenarios are conditional fill approximations, not IOC depth simulations.

Historical membership is today's permitted list, and adjustment vintages are unavailable. No independent untouched out-of-sample dates remain. Native practice data cover only 16 sessions and cannot establish a 20-session result. This research does not certify official eligibility.

## Recommendation

**C — No defensible edge established.** New untouched history and executable price validation are needed before advancing to machine learning. The next practical work is to reconcile adjusted daily prices against native ticks and validate an order adapter on available sessions.
