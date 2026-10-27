# Rollback

The repository began on unborn `main`, with all project files untracked. `git switch -c research/phase3-portfolio` failed to write `.git/HEAD.lock` in the sandbox; `git status` still showed `main`. Phase 3 files are isolated under `research_set50_portfolio/`. The preexisting files and data were not modified.

To roll back, first verify all paths to be removed resolve inside `research_set50_portfolio/`, then remove that directory with a native filesystem tool. Do not use `git reset` or clean the whole repository: that would affect the preexisting untracked research. The result manifest records hashes of all 49 daily input files and the Phase 2 schedule. The Phase 1 `phase1_prephase2_sha256.json` and Phase 2 integrity result are additional reference checkpoints.
