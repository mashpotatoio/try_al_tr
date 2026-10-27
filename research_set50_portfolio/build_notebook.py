"""Create and execute a compact, reviewable notebook of actual run artifacts."""
from pathlib import Path
import sys
import nbformat as nbf
from nbclient import NotebookClient

ROOT=Path(__file__).resolve().parent
out=Path(sys.argv[1]).resolve()
nb=nbf.v4.new_notebook()
nb.cells=[
 nbf.v4.new_markdown_cell("# SET50 Phase 3 — 20-session portfolio research\n\nThis notebook reviews recorded real-data portfolio simulations. Evaluation dates were previously exposed in Phase 1 and Phase 2; these are not untouched holdout results."),
 nbf.v4.new_code_cell("from pathlib import Path\nimport pandas as pd\nimport numpy as np\nfrom IPython.display import display, Image\nout=Path(r'"+str(out)+"')\nmanifest=__import__('json').loads((out/'manifest.json').read_text())\nprint(manifest['experiment_id'], 'selected E base:',manifest['development_selected_e_base'])"),
 nbf.v4.new_markdown_cell("## Signal evidence\n\nMomentum20 and SMA20/SMA60 are inconclusive trend hypotheses. Reversal has a stronger one-session rank association, but its top-quintile excess is smaller than round-trip commission. It is used only to reorder near ties."),
 nbf.v4.new_code_cell("display(pd.read_csv(out/'factor_evidence.csv'))"),
 nbf.v4.new_markdown_cell("## Portfolio mechanics\n\nA–D hold six names at 80% target exposure and a 20% stock cap. Equal weight and inverse trailing volatility isolate sizing. C/D add a reversal tie-breaker within 5% of the primary score range. Decisions use only completed prior closes; next opens are modeled with adverse ticks, fees, VAT, 100-share lots and a prior-volume participation cap. E adds rank hysteresis and a 3 percentage-point trade threshold to the development-selected base."),
 nbf.v4.new_code_cell("comparison=pd.read_csv(out/'comparison.csv'); display(comparison.round(4))\nwindows=pd.read_csv(out/'windows.csv'); display(windows.query(\"role == 'evaluation' and scenario == 'official' and exit_rule == 'scheduled'\").groupby('strategy')[['roundtrip_pass','exposure_pass','payoff_pass','drawdown_pass','best_alpha_eligible']].mean())"),
 nbf.v4.new_markdown_cell("## Distribution and economic costs\n\nMeans hide poor windows. The entire per-window record and cost attribution are available below. The one-tick price adjustment applied to revised historical opens is only a sensitivity estimate, because raw-price adjustment vintages are unavailable."),
 nbf.v4.new_code_cell("display(windows.query(\"role == 'evaluation' and scenario == 'official' and exit_rule == 'scheduled'\")[['window','strategy','net_return','excess_return','roundtrips','expected_payoff_thb','best_alpha_eligible']].head(20))\ndisplay(pd.read_csv(out/'cost_attribution.csv').groupby('strategy').mean(numeric_only=True).round(0))"),
 nbf.v4.new_markdown_cell("## Robustness and uncertainty\n\nCost, fill and exit scenarios are exploratory. The uncertainty intervals resample the 24 non-overlapping windows as units, so they do not treat stock-days as independent trials. Market regimes below are ex-post diagnostics."),
 nbf.v4.new_code_cell("display(pd.read_csv(out/'uncertainty.csv').round(4)); display(pd.read_csv(out/'robustness.csv').round(4)); display(pd.read_csv(out/'regimes_ex_post.csv').round(4))"),
 nbf.v4.new_code_cell("for name in ['equity','window_excess','drawdown','exposure','return_distribution','costs','turnover_performance','eligibility','weighting','sensitivity','regimes']:\n    display(Image(filename=str(out/'figures'/(name+'.png'))))"),
 nbf.v4.new_markdown_cell("## Conclusion\n\nCompare A/C and B/D to assess the incremental reversal signal. Check E's natural FIFO completions alongside turnover. These previously exposed periods and adjusted-price execution approximations cannot prove a competition edge. The Phase 4 gate is to validate executable prices and gather fresh chronological data before considering ML.")]
nb.metadata["kernelspec"]={"display_name":"Python 3","language":"python","name":"python3"}
path=ROOT/"notebooks/03_portfolio_research.ipynb";path.parent.mkdir(exist_ok=True)
nbf.write(nb,path)
client=NotebookClient(nb,timeout=300,kernel_name="python3",resources={"metadata":{"path":str(ROOT.parent)}})
client.execute()
nbf.write(nb,path)
print(path, "executed", sum(c.cell_type=="code" for c in nb.cells), "code cells")
