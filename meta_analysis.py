#!/usr/bin/env python3
"""
meta_analysis.py: one combined test over the primary outcome of every preregistered hardware experiment.

Reads the published analysis files from the cloned repos (./repos) and recomputes two primaries
from raw counts (spatial_ramsey z, spatial_bath_spectroscopy phase family). Writes meta_analysis.json
and meta_analysis_table.csv.

Included: preregistered, completed, hardware, with a primary statistic that yields a p-value.
Excluded (listed in the output with the reason): no p-value in the preregistered rule (classification or R^2
rules), stopped/partial runs, non-preregistered experiments, dry runs and simulations.

Combinations (all fixed before computing them, see README section on the page):
  * Fisher over every included p (two-sided where the preregistration was two-sided, one-sided where it was one-sided).
  * Stouffer A: only tests whose preregistration fixed a direction (c_live, c_live_simultaneous).
  * Stouffer B: "memory direction" convention: every test whose effect is defined as active/secret=1 minus
    passive/secret=0, so a positive sign means "the earlier state leaks into the later measurement".
  * Stouffer C (sensitivity): unsigned, |z| from every p, i.e. "is there more deviation than chance, in any direction".
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
R = HERE / "repos"
BELL = R / "qhf-bell-spectator" / "measurement_raw"
QSM = R / "quantum-space-memory" / "measurement_raw"


def J(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def z_from_p(p, sign=1.0, sided=2):
    return float(np.sign(sign) * (stats.norm.isf(p / 2) if sided == 2 else stats.norm.isf(p)))


def spectroscopy_phase(path):
    """P1 phase tomography: phase of Q49 fringe vs theta, s=1 minus s=0, per tau; max |z|, Bonferroni over 5 tau."""
    d = J(path)
    N = d["shots"]
    P = [x for x in d["data"] if x["meta"]["protocol"] == "P1_phase_tomography"]
    taus = sorted({x["meta"]["tau_us"] for x in P})
    fit = {}
    for s in (0, 1):
        for tau in taus:
            pts = [(x["meta"]["theta"], sum(v for k, v in x["counts"].items() if k[::-1][1] == "1") / N)
                   for x in P if x["meta"]["s"] == s and x["meta"]["tau_us"] == tau]
            th = np.array([a for a, _ in pts]); p = np.array([b for _, b in pts])
            X = np.c_[np.ones_like(th), np.cos(th), np.sin(th)]
            beta, *_ = np.linalg.lstsq(X, p, rcond=None)
            amp = np.hypot(beta[1], beta[2])
            W = np.diag(1 / np.maximum(p * (1 - p) / N, 1e-9))
            cov = np.linalg.inv(X.T @ W @ X)
            Jv = np.array([0, -beta[2] / amp ** 2, beta[1] / amp ** 2])
            fit[(s, tau)] = (np.arctan2(beta[2], beta[1]), float(np.sqrt(Jv @ cov @ Jv)))
    rows = []
    for tau in taus:
        (a, sa), (b, sb) = fit[(0, tau)], fit[(1, tau)]
        dphi = float(np.angle(np.exp(1j * (b - a))))
        se = float(np.hypot(sa, sb))
        rows.append({"tau_us": tau, "dphi_deg": np.rad2deg(dphi), "se_deg": np.rad2deg(se), "z": dphi / se})
    zmax = max(rows, key=lambda r: abs(r["z"]))
    p_bonf = min(1.0, len(rows) * 2 * stats.norm.sf(abs(zmax["z"])))
    return rows, zmax, p_bonf


def main():
    T, X = [], []

    a = J(BELL / "c_live/20261107T012230Z/analysis.json")
    T.append(dict(exp="c_live", run="20261107T012230Z", backend=a["backend"], repo="qhf-bell-spectator",
                  prereg="docs/PREREGISTRATION-c_live.md", metric="Bell coherence c, F minus N, paired by block",
                  effect=a["mean_diff"], n=a["complete_blocks"], p=a["p_one_sided"], sided=1, direction_prereg=True,
                  memory_direction=True, source="measurement_raw/c_live/20261107T012230Z/analysis.json"))
    a = J(BELL / "c_live_simultaneous/20261107T023824Z/analysis.json")
    T.append(dict(exp="c_live_simultaneous", run="20261107T023824Z", backend=a["backend"], repo="qhf-bell-spectator",
                  prereg="docs/PREREGISTRATION-c_live_simultaneous.md", metric="Bell coherence c, F minus N, simultaneous blocks",
                  effect=a["mean_diff"], n=a["complete_blocks"], p=a["p_one_sided"], sided=1, direction_prereg=True,
                  memory_direction=True, source="measurement_raw/c_live_simultaneous/20261107T023824Z/analysis.json"))
    for run, pr in (("20261107T032204Z", "docs/PREREGISTRATION-qpu_vs_rng.md"), ("20261107T041028Z", "docs/PREREGISTRATION-qpu_vs_rng_replication.md")):
        a = J(BELL / f"qpu_vs_rng/{run}/analysis.json")
        be = "ibm_marrakesh" if run.startswith("20261107T03") else "ibm_kingston"
        T.append(dict(exp="qpu_vs_rng" + ("" if run.startswith("20261107T03") else "_replication"), run=run, backend=be,
                      repo="qhf-bell-spectator", prereg=pr, metric="centroid frequency f, QPU-fed minus RNG-fed fluid",
                      effect=a["primary"]["mean_D"], n=a["num_replicates"], p=a["primary"]["exact_permutation_p"], sided=2,
                      direction_prereg=False, memory_direction=False, source=f"measurement_raw/qpu_vs_rng/{run}/analysis.json"))
    a = J(QSM / "space_memory/20261107T050740Z/analysis.json")
    T.append(dict(exp="space_memory", run="20261107T050740Z", backend=a["backend"], repo="quantum-space-memory",
                  prereg="docs/PREREGISTRATION.md (= PREREGISTRATION-space_memory.md)", metric="P(1) in job B, secret bit 1 minus 0",
                  effect=a["primary"]["Delta"], n=a["pairs"], p=a["primary"]["p_two_sided"], sided=2, direction_prereg=False,
                  memory_direction=True, source="measurement_raw/space_memory/20261107T050740Z/analysis.json"))
    a = J(QSM / "spatial_ramsey/20261107T060617Z/analysis.json")
    zr = a["spatial_phase_shift_rad"] / a["combined_error_rad"]
    T.append(dict(exp="spatial_ramsey", run="20261107T060617Z", backend=a["backend"], repo="quantum-space-memory",
                  prereg="docs/PREREGISTRATION-spatial_ramsey_probe.md", metric="Ramsey phase of Q49, pumped minus vacuum (deg)",
                  effect=a["spatial_phase_shift_deg"], n=1, p=float(2 * stats.norm.sf(abs(zr))), sided=2, direction_prereg=False,
                  memory_direction=False, source="measurement_raw/spatial_ramsey/20261107T060617Z/analysis.json (z = shift / combined error, recomputed)"))
    rows, zmax, pb = spectroscopy_phase(QSM / "spatial_bath_spectroscopy/20261107T062103Z/raw_results.json")
    T.append(dict(exp="spatial_bath_spectroscopy", run="20261107T062103Z", backend="ibm_kingston", repo="quantum-space-memory",
                  prereg="docs/PREREGISTRATION-spatial_bath_spectroscopy.md",
                  metric=f"phase of Q49, s=1 minus s=0, largest of 5 delays (tau={zmax['tau_us']:g} us), Bonferroni x5",
                  effect=zmax["dphi_deg"], n=5, p=pb, sided=2, direction_prereg=False, memory_direction=False,
                  source="measurement_raw/spatial_bath_spectroscopy/20261107T062103Z/raw_results.json (recomputed from counts)"))
    for fam, run, pr in (("zero_iq", "20261107T073452Z", "docs/PREREGISTRATION-zero_iq_memory.md"),
                         ("zero_iq_energy_matched", "20261107T075634Z", "docs/PREREGISTRATION-zero_iq_energy_matched.md")):
        a = J(QSM / f"{fam}/{run}/analysis.json")
        T.append(dict(exp=fam, run=run, backend=a["backend"], repo="quantum-space-memory", prereg=pr,
                      metric="centre x0 of job B ground-state IQ cloud along 0->1 axis, secret 1 minus 0",
                      effect=a["primary"]["Delta"], n=a["pairs"], p=a["primary"]["p_two_sided"], sided=2, direction_prereg=False,
                      memory_direction=True, source=f"measurement_raw/{fam}/{run}/analysis.json"))

    X += [
        dict(exp="qoi-core GPE-QPU closed loop (2026-11-02)", reason="preregistered rule is a mode count (M1 >= 4 modes), no p-value"),
        dict(exp="angle_calibration Marrakesh + Kingston (045219Z, 045336Z)", reason="rule is R^2 > 0.85 of a sine model, no p-value; power about 5% (earlier audit)"),
        dict(exp="memory_decay_sweep (060046Z)", reason="classification rule on T_mem (232 us, T1 class), no p-value; it is a characterisation, not a test of H1"),
        dict(exp="c_live_simultaneous 015449Z (9 blocks) and 020117Z (5 blocks)", reason="stopped runs, below the preregistered block count, never analysed in the repo"),
        dict(exp="quantum-anchor, quantum-anchored-memory, quantum-delayed-sync, wave-quantum, scs-quantum, quantum-hydrodynamic-feedback (Oct 2026)",
             reason="no preregistration file; several outcomes were defined or rewritten after the data"),
        dict(exp="p = 0.03 entropy metric (Marrakesh 80 runs, 2026-11-02)", reason="chosen after looking at the data"),
        dict(exp="all dry runs and simulations", reason="not hardware"),
    ]

    df = pd.DataFrame(T)
    df["sign"] = np.sign(df.effect)
    df["z_signed"] = [z_from_p(p, s, sd) for p, s, sd in zip(df.p, df.sign, df.sided)]
    df["z_abs"] = [abs(z_from_p(p, 1, 2 if sd == 2 else 1)) for p, sd in zip(df.p, df.sided)]
    df["pass_own_rule"] = False

    k = len(df)
    fisher_stat = float(-2 * np.log(df.p).sum())
    fisher_p = float(stats.chi2.sf(fisher_stat, 2 * k))
    A = df[df.direction_prereg]
    zA = float(A.z_signed.sum() / np.sqrt(len(A)))
    B = df[df.memory_direction]
    zB = float(B.z_signed.sum() / np.sqrt(len(B)))
    zC = float(df.z_abs.sum() / np.sqrt(k))
    # |z| of a null test is half-normal: mean sqrt(2/pi), var 1-2/pi
    zC_std = float((df.z_abs.sum() - k * np.sqrt(2 / np.pi)) / np.sqrt(k * (1 - 2 / np.pi)))
    n_pos = int((df.sign > 0).sum())
    sign_p = float(stats.binomtest(n_pos, k, 0.5).pvalue)
    # one-sided dependence-robust check: Bonferroni on the smallest p (valid under any dependence)
    bonf_min = float(min(1.0, df.p.min() * k))

    res = {
        "included_tests": k,
        "fisher": {"chi2": fisher_stat, "df": 2 * k, "p": fisher_p},
        "stouffer_A_preregistered_direction": {"tests": list(A.exp), "Z": zA, "p_one_sided": float(stats.norm.sf(zA))},
        "stouffer_B_memory_direction": {"tests": list(B.exp), "Z": zB, "p_one_sided": float(stats.norm.sf(zB)),
                                        "p_two_sided": float(2 * stats.norm.sf(abs(zB)))},
        "stouffer_C_unsigned_halfnormal": {"Z": zC_std, "p_one_sided": float(stats.norm.sf(zC_std)),
                                           "note": "sum of |z| standardised against the half-normal null"},
        "signs": {"positive": n_pos, "of": k, "binomial_p_two_sided": sign_p},
        "smallest_p": {"test": df.loc[df.p.idxmin(), "exp"], "p": float(df.p.min()), "bonferroni_over_all": bonf_min},
        "spectroscopy_per_tau": rows,
        "bounds_99pct": [{"test": r.exp, "effect": float(r.effect), "se_from_p": float(abs(r.effect) / abs(r.z_signed)),
                          "ci99": [float(r.effect - 2.576 * abs(r.effect) / abs(r.z_signed)), float(r.effect + 2.576 * abs(r.effect) / abs(r.z_signed))]}
                         for r in df.itertuples() if r.exp in ("space_memory", "zero_iq", "zero_iq_energy_matched", "c_live", "c_live_simultaneous")],
        "excluded": X,
        "independence": ("Not fully independent: zero_iq, zero_iq_energy_matched, space_memory, spatial_ramsey and "
                         "spatial_bath_spectroscopy all ran on ibm_kingston qubits 48-50 within three hours; c_live and "
                         "c_live_simultaneous both on ibm_marrakesh; the two qpu_vs_rng runs share code. Positive "
                         "correlation makes Fisher and Stouffer anti-conservative (combined p too small), so it cannot "
                         "hide a signal; it can only exaggerate one. The Bonferroni bound on the smallest p is valid "
                         "under any dependence."),
    }
    df.to_csv(HERE / "meta_analysis_table.csv", index=False)
    (HERE / "meta_analysis.json").write_text(json.dumps(res, indent=2, default=float), encoding="utf-8")
    with pd.option_context("display.width", 220, "display.max_columns", 20):
        print(df[["exp", "backend", "effect", "n", "p", "sided", "z_signed"]])
    print(json.dumps({k2: v for k2, v in res.items() if k2 not in ("excluded", "independence")}, indent=1, default=float))


if __name__ == "__main__":
    main()
