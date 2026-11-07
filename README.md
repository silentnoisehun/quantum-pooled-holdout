# Pooled hardware measurements: exploration / confirmation split

All quantum hardware measurements from the ten public repositories of silentnoisehun (Oct 7 to Nov 7, 2026) in one table, split into an exploration half and a held-out confirmation half before anyone searches them, plus a combined test of every preregistered primary result.

- `build_dataset.py`: builds `data/` from the repos (clone them into `./repos` at the commits in `split_manifest.json`). Schema: `schema.md`.
- `split.py`: the deterministic split. `python split.py verify` checks the halves against `split_manifest.json`.
- `docs/PREREGISTRATION-pooled_holdout.md`: the rules for exploration, candidates and confirmation.
- `meta_analysis.py`, `meta_analysis.json`, `meta_analysis_table.csv`: the combined test.

Reproduce:

```
mkdir repos && cd repos
for r in qhf-bell-spectator qhf-core qhf-topological-vortex quantum-anchor quantum-anchored-memory quantum-delayed-sync quantum-hydrodynamic-feedback quantum-space-memory scs-quantum wave-quantum; do git clone https://github.com/silentnoisehun/$r.git; done
# then check out each repo at the commit listed in split_manifest.json -> source_repos_at_commit
cd ..
pip install pandas pyarrow numpy scipy
python build_dataset.py --repos repos --out data
python split.py verify
python meta_analysis.py
```
