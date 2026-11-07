# Preregistration: Exploration/Confirmation Split of the Pooled Quantum Hardware Dataset

**Author:** Máté Róbert (ORCID: 0009-0003-3986-6039)  
**Repository:** https://github.com/silentnoisehun/quantum-pooled-holdout  
**Date of Registration:** 2026-11-07T08:50:00Z  
**Manifest:** `split_manifest.json` (Seed: 20261115)  
**Confirmation Holdout Hash:** `023f870beeb9608ef62914e064b1f59b6d15bc00029f903ccd23b0fac6bc746f`  

---

## 1. Objective & Scientific Integrity

Between October 7 and November 7, 2026, 10 open research repositories executed 1,016 quantum hardware jobs (5.11 million physical measurement shots) across IBM Heron r2 processors (`ibm_marrakesh`, `ibm_kingston`, `ibm_fez`) and IQM Garnet.

An omnibus meta-analysis across all 9 frozen preregistered tests yielded:
* Fisher combined test: $\chi^2 = 24.60$ (df=18), $p = 0.135$
* Directed Stouffer $Z$ test: $Z = +0.29$, $p = 0.386$

To explore whether unmodeled physical interactions, temporal drift correlations, or cross-qubit crosstalk exist in the raw dataset without post-hoc circularity, we establish an immutable **50/50 Exploration vs. Confirmation Holdout Split**.

---

## 2. Split Rules & Blinding Protocol

1. **Stratification Unit:** Independent blocks, pairs, or iterations.
2. **Deterministic Partitioning:** Generated via pseudorandom seed `20261115`.
3. **Exploration Half:** Unlocked immediately. Researchers may evaluate arbitrary metrics, noise spectra, or correlations.
4. **Candidate Registration:** Before unlocking the confirmation set, at most 5 explicit mathematical candidate rules must be committed to `docs/CANDIDATES-pooled_holdout.md` with frozen Python scripts.
5. **Confirmation Testing:** Evaluated strictly once. Multiple testing is adjusted via Holm-Bonferroni correction at family-wise error rate $\alpha = 0.01$.
6. **Falsification & Replication:** Any candidate surviving confirmation holdout testing constitutes a hypothesis requiring pre-registered prospective hardware replication on a distinct QPU backend.
