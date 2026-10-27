"""Verify and execute the portable Phase 3.5 notebook against bundled results."""
from pathlib import Path
import json
import nbformat
from nbclient import NotebookClient

root=Path(__file__).resolve().parent
publication=root.parent
result=root/'published_results/20261027T174032Z'
reproduction=json.loads((result/'phase3_reconciliation.json').read_text())
assert reproduction['matched_rows']==reproduction['saved_rows']==356
assert max(reproduction['max_absolute_difference'].values())<=reproduction['tolerance']
assert (result/'tick_size_validation.csv').is_file()
notebook=nbformat.read(root/'notebooks/035_execution_diagnostics.ipynb',as_version=4)
NotebookClient(notebook,timeout=180,kernel_name='python3',resources={'metadata':{'path':str(publication)}}).execute()
code=[c for c in notebook.cells if c.cell_type=='code']
assert len(code)==12 and all(c.execution_count is not None for c in code)
assert not any(o.output_type=='error' for c in code for o in c.outputs)
print('Phase 3.5 publication: PASS;',len(code),'executed code cells')
