# Factor methodology

All features use completed daily data through signal session `t`. Each factor is oriented so a **higher** value represents its stated positive-return hypothesis. The input is the current vendor-revised OHLCV file; its historical point-in-time vintages are unavailable. Every label is `Open(t+1+h)/Open(t+1)-1` on the common SET50 trading calendar. The SET50 target uses the same dates. If the required open path is incomplete, the label is missing.

| Factor | Formula or construction | Hypothesis and limitation |
|---|---|---|
| Momentum 3/5/10/20 | `Close(t)/Close(t-N)-1` | Recent winners continue; may reverse or merely reflect market movement. |
| Relative 3/5/10/20 | Stock momentum minus SET50 momentum over N | Outperformance may persist; subtracting a common benchmark leaves same-date rankings exactly unchanged. |
| Reversal 1/3/5 | Negative of N-session close return | Recent losers rebound; crash continuation can defeat it. |
| RSI14 oversold | `100 - Wilder RSI(14)` | Lower RSI becomes a higher reversal score. A high score is a hypothesis, not an automatic buy. |
| MA20 reversion | `-(Close/SMA20-1)` | Price below its trailing mean may rebound; a persistent downtrend can dominate. |
| Low volatility 10/20 | Negative standard deviation of trailing daily close returns | Low-volatility names may have better forward returns; this is distinct from risk-based sizing. |
| Low normalized ATR14 | Negative mean true range divided by close | Lower trading range may signal a quality or risk effect; adjusted OHLC can distort ranges near actions. |
| Volatility-normalized momentum 5/20 | Momentum divided by 20-session realized volatility | Momentum may be more reliable when its move is large relative to past risk. Zero volatility is undefined. |
| Volume surprise | `Volume(t)/mean(Volume(t-20:t-1))` | Unusual volume may change signal quality; it is not inherently bullish. |
| Volume 5/20 | Trailing 5-session mean volume divided by trailing 20-session mean | Sustained activity may contain information; volume adjustment provenance is unknown. |
| Price-volume confirmation | Five-session momentum times volume surprise | Volume may amplify recent price moves; sign is inherited from momentum. |
| Log trading value20 | Log of trailing mean `Close × Volume` | Liquidity may predict outcomes or simply improve feasibility; this is a proxy, not reported turnover. |
| Above SMA20 | `Close/SMA20-1` | Short trend continuation; overlaps with momentum. |
| SMA20 above SMA60 | `SMA20/SMA60-1` | Medium trend continuation; needs 60 complete sessions. |
| Trend strength5 | `SMA20(t)/SMA20(t-5)-1` | Slope of the existing trend may matter; correlated with other trend factors. |

For example, if closes five sessions apart are THB 100 and THB 105, five-session momentum is `105/100-1 = 5%`. If SET50 rose 2% over those same sessions, relative strength is 3%. Every stock loses the same 2% on that date, so ranks are identical. If entry opens at THB 106 and the open five sessions later is THB 108, the forward label is `108/106-1 = 1.887%`; it is independent of the earlier 5% move.

Other factor examples use illustrative completed data, not observations from this experiment. A three-session return of −4% gives a reversal score of +4%. Wilder average gains of 1 and losses of 2 give RSI 33.33 and the oriented oversold score 66.67. A THB 90 close with SMA20 of THB 100 gives MA-reversion score +10% and above-SMA20 score −10%. If ten-session return standard deviation is 2%, low-volatility score is −0.02; a mean true range of THB 2 at a THB 100 close gives low-ATR score −0.02. Five-session momentum of 6% with 20-session volatility of 2% gives volatility-normalized momentum 3. Volume of 12 million shares versus a prior 20-session mean of 8 million gives volume surprise 1.5; five- and twenty-session means of 10 and 8 million give volume ratio 1.25. Five-session momentum of 6% times volume surprise 1.5 gives price-volume confirmation 0.09. Mean daily trading value of THB 100 million gives log-trading-value score `ln(100,000,000)`. SMA20 of THB 105 and SMA60 of THB 100 gives SMA-ratio trend +5%; SMA20 rising from THB 100 to THB 102 over five sessions gives trend strength +2%. Every example's newest input is session `t`, never the forward-return entry or exit.

## Diagnostics

For each date, Pearson IC is the correlation of factor scores with future stock returns. Rank IC is Pearson correlation of their average ranks, equivalent to Spearman's coefficient with ties. Constant or too-small cross-sections are undefined and omitted with a status; zero is never substituted. IC information ratio here is **mean daily IC divided by sample standard deviation of daily IC**, unannualized. It describes date-to-date stability, not a Sharpe ratio.

Stocks are grouped into quintiles with at least 30 valid names, terciles with 15–29, and no quantiles below 15. Equal scores share an average rank and therefore the same group. Collapsed groups are identified. Quantile means compare future returns by signal strength; the top-minus-bottom difference is a long-short **diagnostic**, unavailable as a direct long-only competition trade. Top-group absolute and SET50-relative returns are also reported. Group means, ICs and 95% intervals are shown across all five horizons.

The predeclared regimes use SET50 close relative to its trailing SMA60, positive versus negative trailing 20-session momentum, and 20-session realized volatility relative to the **previously observed** expanding median. These are date-level conditions, never cross-sectional scores. The four conditional tests in the configuration are exploratory; their sample sizes must accompany interpretation.
