# Candidates File: Pooled Exploration / Confirmation Protocol

Date: 2026-11-07
Author: Máté Róbert (ORCID 0009-0003-3986-6039)
Preregistration: `docs/PREREGISTRATION-pooled_holdout.md`

## Exploration Summary
The exploration half (204 units, 511 hardware jobs across IBM Marrakesh, Kingston, Fez, and IQM Garnet) was materialized and systematically audited using `explore_ten_perspectives.py`.

Ten orthogonal exploratory perspectives were tested:
1. `temporal_drift_autocorr`: Lag-1 autocorrelation of shot sequences (p = 0.617) -> NULL
2. `odd_even_shot_asymmetry`: Two-sample KS test on parity shot distributions (p = 0.442) -> NULL
3. `iq_cloud_radial_kurtosis`: Excess kurtosis of raw transmon IQ clouds (p = 0.589) -> NULL
4. `cross_qubit_spatial_correlation`: Pairwise Pearson correlation between spectator qubits (p = 0.731) -> NULL
5. `high_order_cumulant_skew`: Third-moment skewness in bitstring frequencies (p = 0.498) -> NULL
6. `state_dependent_decay_contrast`: |0> vs |1> relaxation differential contrast (p = 0.812) -> NULL
7. `inter_job_delay_scaling`: Dependence of baseline shift on idle cooldown time (p = 0.354) -> NULL
8. `transmon_frequency_detuning_drift`: Centroid stability across frequency bands (p = 0.684) -> NULL
9. `phase_quadrature_orthogonality`: Deviations from 90-degree IQ quadrature angles (p = 0.279) -> NULL
10. `spatial_vortex_phase_winding`: Non-trivial topological phase circulation around spectator loops (p = 0.415) -> NULL

## Candidate Nomination: None (0 Candidates)
In accordance with Section 52 of `docs/PREREGISTRATION-pooled_holdout.md`:
> *"If no candidate is committed, the protocol ends with no result."*

None of the ten perspectives achieved an uncorrected p-value below 0.05 or an effect size warranting preregistered confirmatory extraction. Under the pre-established rules of scientific integrity, no exploratory artifacts will be p-hacked into candidates.

## Conclusion on Passive Quantum Space Memory
The hypothesis of passive, persistent thermal/quantum remnants in transmon spectator chips
across independent batch jobs is **not supported**. No effect was detectable within the
sensitivity of the pooled design: the combined test over the nine preregistered primary
results gives Fisher chi2 = 24.63 (df = 18, p = 0.135), and the exploration half produced no
candidate with a p-value below 0.05 that would survive the Holm correction.

A null result **bounds** the effect; it does not prove the hypothesis false. The bound that
this design excludes is the appropriate statement, and it is set by the smallest effect the
individual campaigns could have seen (roughly one percentage point in arm probability at
1,000 shots per arm), not by the p-values alone.

All future efforts are directed toward the **Active Nonlinear Feedback Reservoir Architecture** (`quantum-feedback-memory-space`), where information is maintained dynamically via closed-loop transmon actuation and Gross-Pitaevskii topological soliton stability.
