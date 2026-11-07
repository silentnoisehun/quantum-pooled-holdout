# Quantum Pooled Holdout: Unified Dataset, Meta-Analysis & Preregistered Split Verification

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![ORCID](https://img.shields.io/badge/ORCID-0009--0003--3986--6039-green.svg)](https://orcid.org/0009-0003-3986-6039)

Unified open dataset and blinded exploration/confirmation split framework archiving all superconducting quantum hardware campaigns (10 repositories, 1,016 QPU jobs, 5.11 million shots, IBM Heron r2 & IQM Garnet) conducted between October 7 and November 7, 2026.

**Author:** Máté Róbert (Rongyász)  
**Affiliation:** Silent Coder Labs  
**ORCID:** [0009-0003-3986-6039](https://orcid.org/0009-0003-3986-6039)  
**Contact:** materobi86@gmail.com  

---

## 🔬 Overall Meta-Analysis: Omnibus Test Across 9 Preregistered Campaigns

Aggregating all 9 frozen, preregistered hardware campaigns under omnibus statistical testing:
* **Fisher Combined Omnibus Test:**
  $$\chi^2 = 24.60,\quad \text{df} = 18,\quad p = 0.135$$
* **Directed Stouffer $Z$ Test ("Memory / Active" Hypothesis):**
  $$Z = +0.29,\quad p = 0.386$$
* **Directed Stouffer $Z$ Test ($c_{\text{live}}$ Feedback):**
  $$Z = +0.98,\quad p = 0.164$$

### Campaign Summary Table

| Campaign | Hardware Backend | Effect Metric | Result | Decision $p$ | Preregistered Verdict |
|---|---|---|---|---|---|
| `c_live` | `ibm_marrakesh` (60 blocks) | $\Delta c$ | $+0.00254$ | $p = 0.165$ (1-sided) | $H_0$ Confirmed (Null) |
| `c_live_simultaneous` | `ibm_marrakesh` (60 blocks) | $\Delta c$ | $+0.00021$ | $p = 0.341$ (1-sided) | $H_0$ Confirmed (Null) |
| `qpu_vs_rng` | `ibm_marrakesh` (20 repl.) | $D(f)$ | $+0.00147$ | $p = 0.411$ | $H_0$ Confirmed (Null) |
| `qpu_vs_rng_replication` | `ibm_kingston` (20 repl.) | $D(f)$ | $+0.00226$ | $p = 0.252$ | $H_0$ Confirmed (Null) |
| `space_memory` | `ibm_kingston` (33 pairs) | $\Delta P(1)$ | $+0.00023$ | $p = 0.361$ | $H_0$ Confirmed (Null) |
| `spatial_ramsey` | `ibm_kingston` (1 batch) | $\Delta\Phi$ | $+0.36^\circ \pm 0.62^\circ$ | $p = 0.560$ | $H_0$ Confirmed (Null) |
| `spatial_bath_spectroscopy` | `ibm_kingston` (92 circ.) | Max $\Delta\Phi$ | $-1.9^\circ \pm 0.5^\circ$ | $p = 0.027$ (corr.) | $H_0$ Confirmed (Reset Crosstalk) |
| `zero_iq_memory` | `ibm_kingston` (40 pairs) | $\Delta x_0$ | $-0.00069$ | $p = 0.555$ | $H_0$ Confirmed (Null) |
| `zero_iq_energy_matched` | `ibm_kingston` (40 pairs) | $\Delta x_0$ | $-0.00135$ | $p = 0.286$ | $H_0$ Confirmed (Null) |

---

## 🛡️ Pre-Commit Split Protocol (Explore vs. Confirm)

To eliminate post-hoc data dredging while enabling unbiased hypothesis generation, the dataset is stratified 50/50:
1. **Stratification Unit:** Independent block, pair, or iteration unit.
2. **Seed:** `20261115` (frozen in `split_manifest.json`).
3. **Exploration Half (50%):** Open for exploratory pattern search and anomaly discovery.
4. **Confirmation Holdout Half (50%):** Cryptographically hashed and locked. It is unlocked **only once**, evaluating at most 5 candidate rules with Holm-Bonferroni correction ($\alpha = 0.01$).

---

## 📁 Repository Layout

```
├── docs/
│   └── PREREGISTRATION-pooled_holdout.md   # Frozen preregistration protocol
├── scripts/
│   ├── build_dataset.py                    # Consolidates raw JSONs into parquet/jsonl
│   ├── split.py                            # 50/50 stratification and verification tool
│   └── meta_analysis.py                   # Computes Fisher chi2 and Stouffer Z
├── split/
│   ├── explore_units.csv                   # Unit IDs in the exploration set
│   └── confirm_units.csv                   # Unit IDs in the holdout confirmation set
├── schema.md                               # Unified data schema description
└── split_manifest.json                     # Git commit hashes of all 10 source repos
```
