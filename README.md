# Pooled hardware measurements: exploration / confirmation split

> **Status (2026-11-09):** protocol complete, **no candidate nominated, no result** (Section 52).
> The confirmation half was never analysed. A null here bounds the effect; it does not confirm
> the null hypothesis.

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

## What is actually sealed (corrected 2026-11-09)

The **unit lists** and the **data entries** of the confirmation half are both present in this
repository: `data/counts.parquet` contains every job, and `split/confirm_units.csv` says which
units belong to the sealed half. So the seal is a **commitment, not a technical lock**: nothing
prevents anyone (including the author) from reading the confirmation values.

What the seal does guarantee, and what this file records:

- the split was fixed by `split.py` before any candidate existed, and it is reproducible from
  `split_manifest.json` (seed + two SHA-256 digests per half);
- no candidate was ever committed, so per Section 52 the protocol ended with no result, and
  the confirmation half was never analysed;
- if a candidate is ever proposed later, it must be committed **before** the confirmation
  values are first read, and the reading must be done by a script committed in the same
  commit as the candidate.

If you want a lock that does not depend on trust, publish only the unit/job-id lists and the
digests, keep `data/` for the exploration half, and release the confirmation rows with a
timestamped archive **after** the candidate commit. That is the recommended fix; this
repository keeps both halves because the dataset is also the reproduction artefact.
