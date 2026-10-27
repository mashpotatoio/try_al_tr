"""Verify the portable result snapshot and execute its notebook in memory."""
from pathlib import Path
import hashlib
import json
import nbformat
from nbclient import NotebookClient

root = Path(__file__).resolve().parent
publication = root.parent
result = root / "published_results/20261027T162905Z_979c875c"
manifest = json.loads((result / "manifest.json").read_text(encoding="utf-8"))
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

assert digest(result / "config.json") == manifest["config_sha256"]
for name, expected in manifest["source_hashes"].items():
    assert digest(root / name) == expected, name
for name in ["windows.csv", "orders.csv", "holdings.csv", "fifo_roundtrips.csv", "eligibility_audit.csv", "comparison.csv"]:
    assert (result / name).is_file(), name
assert len(list((result / "figures").glob("*.png"))) == 11
assert json.loads((result / "verification.json").read_text())["pass"] is True
notebook = nbformat.read(root / "notebooks/03_portfolio_research.ipynb", as_version=4)
NotebookClient(notebook, timeout=300, kernel_name="python3", resources={"metadata": {"path": str(publication)}}).execute()
print("Publication snapshot and notebook: PASS; code cells:", sum(c.cell_type == "code" for c in notebook.cells))
