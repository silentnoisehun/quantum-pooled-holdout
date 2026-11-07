#!/usr/bin/env python3
"""
explore_ten_perspectives.py: Comprehensive exploratory analysis of the exploration half (split/explore).
Strictly adheres to the preregistration: searches only split/explore.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
EXP = HERE / "split" / "explore"

def run_all():
    print("=====================================================================")
    print("EXPLORATION HALF ANALYSIS: 10 UNUSUAL PERSPECTIVES")
    print("=====================================================================\n")

    # Load data
    counts_df = pd.read_parquet(EXP / "counts.parquet")
    iq_df = pd.read_parquet(EXP / "iq_shots.parquet")
    mem_df = pd.read_parquet(EXP / "shot_memory.parquet")

    results = {}

    # -------------------------------------------------------------------------
    # PERSPECTIVE 1: HIGHER MOMENTS OF THE 0-CLOUD (Variance, Skewness, Kurtosis)
    # -------------------------------------------------------------------------
    print("--> 1. Higher Moments of the 0-Cloud (zero_iq & zero_iq_energy_matched)")
    # Filter for B job main circuit (measuring the 0-cloud immediately after A)
    main_iq = iq_df[(iq_df.job_role == "B") & (iq_df.circuit == "main") & (iq_df.data_class == "hardware")].copy()
    
    # We analyze projection along cal0 -> cal1 axis per pair
    # First get cal centroids per pair, family, qubit
    cal = iq_df[(iq_df.job_role == "B") & (iq_df.circuit.isin(["cal0", "cal1"])) & (iq_df.data_class == "hardware")].copy()
    cals = cal.groupby(["family", "pair", "qubit_pos", "circuit"])[["I", "Q"]].mean().unstack("circuit")
    
    # Merge calibration centers back
    main_iq = main_iq.set_index(["family", "pair", "qubit_pos"])
    v_I = cals["I"]["cal1"] - cals["I"]["cal0"]
    v_Q = cals["Q"]["cal1"] - cals["Q"]["cal0"]
    norm_sq = v_I**2 + v_Q**2
    
    main_iq["v_I"] = v_I
    main_iq["v_Q"] = v_Q
    main_iq["norm_sq"] = norm_sq
    main_iq["c0_I"] = cals["I"]["cal0"]
    main_iq["c0_Q"] = cals["Q"]["cal0"]
    main_iq = main_iq.reset_index()
    
    # Projected coordinate: u = ((I - c0_I)*v_I + (Q - c0_Q)*v_Q) / norm_sq
    main_iq["u"] = ((main_iq["I"] - main_iq["c0_I"]) * main_iq["v_I"] + 
                    (main_iq["Q"] - main_iq["c0_Q"]) * main_iq["v_Q"]) / main_iq["norm_sq"]
    
    # Compute per pair-qubit stats for s=0 vs s=1
    stats_list = []
    for (fam, pair, qpos, s), g in main_iq.groupby(["family", "pair", "qubit_pos", "secret_bit"]):
        vals = g["u"].values
        stats_list.append({
            "family": fam, "pair": pair, "qubit_pos": qpos, "secret_bit": s,
            "mean": np.mean(vals),
            "var": np.var(vals),
            "skew": float(stats.skew(vals)),
            "kurt": float(stats.kurtosis(vals)),
            "tail_3sigma": np.mean(vals > 3 * np.std(vals))
        })
    df_moments = pd.DataFrame(stats_list)
    
    # Compare s=1 vs s=0 across paired samples
    p1 = {}
    for metric in ["var", "skew", "kurt", "tail_3sigma"]:
        s0 = df_moments[df_moments.secret_bit == 0][metric].values
        s1 = df_moments[df_moments.secret_bit == 1][metric].values
        tt = stats.ttest_ind(s1, s0, equal_var=False)
        diff = np.mean(s1) - np.mean(s0)
        p1[metric] = {"diff": float(diff), "p": float(tt.pvalue), "s0_mean": float(np.mean(s0)), "s1_mean": float(np.mean(s1))}
        print(f"    Metric: {metric:12s} | Diff (s1 - s0): {diff:+.6f} | p-value: {tt.pvalue:.4f}")
    results["perspective_1_higher_moments"] = p1

    # -------------------------------------------------------------------------
    # PERSPECTIVE 2: ORDER / HYSTERESIS ON CALIBRATION PULSES (cal0 vs cal1 separation)
    # -------------------------------------------------------------------------
    print("\n--> 2. Calibration Separation Modulation (cal1 - cal0 vs secret bit)")
    cals_reset = cals.reset_index()
    cals_reset["dist"] = np.sqrt((cals_reset["I"]["cal1"] - cals_reset["I"]["cal0"])**2 + 
                                 (cals_reset["Q"]["cal1"] - cals_reset["Q"]["cal0"])**2)
    # Merge secret bit
    s_map = df_moments.groupby(["family", "pair", "qubit_pos"])["secret_bit"].first().to_dict()
    cals_reset["secret_bit"] = [s_map.get((f, p, q)) for f, p, q in zip(cals_reset.family, cals_reset.pair, cals_reset.qubit_pos)]
    
    d0 = cals_reset[cals_reset.secret_bit == 0]["dist"].dropna()
    d1 = cals_reset[cals_reset.secret_bit == 1]["dist"].dropna()
    tt_dist = stats.ttest_ind(d1, d0, equal_var=False)
    diff_dist = float(np.mean(d1) - np.mean(d0))
    print(f"    Cal separation distance diff: {diff_dist:+.6f} | p-value: {tt_dist.pvalue:.4f}")
    results["perspective_2_cal_separation"] = {"diff": diff_dist, "p": float(tt_dist.pvalue)}

    # -------------------------------------------------------------------------
    # PERSPECTIVE 3: WITHIN-JOB POSITIVE CONTROL (ctrl_u0 vs ctrl_u1)
    # -------------------------------------------------------------------------
    print("\n--> 3. Within-Job Reset Residual Modulation (ctrl_u0 vs ctrl_u1)")
    ctrl = iq_df[(iq_df.job_role == "B") & (iq_df.circuit.isin(["ctrl_u0", "ctrl_u1"])) & (iq_df.data_class == "hardware")].copy()
    # ctrl_u0 is reset after ground; ctrl_u1 is reset after X pulse
    # Does previous job A state correlate with reset infidelity in ctrl_u0?
    ctrl_u0 = ctrl[ctrl.circuit == "ctrl_u0"]
    # Mean I/Q in register c2 for s=0 vs s=1
    ctrl_stats = ctrl_u0.groupby(["family", "pair", "qubit_pos", "secret_bit"])[["I", "Q"]].mean().reset_index()
    c0_s0 = ctrl_stats[ctrl_stats.secret_bit == 0]["I"]
    c0_s1 = ctrl_stats[ctrl_stats.secret_bit == 1]["I"]
    tt_ctrl = stats.ttest_ind(c0_s1, c0_s0)
    print(f"    ctrl_u0 post-reset I diff: {np.mean(c0_s1)-np.mean(c0_s0):+.6f} | p-value: {tt_ctrl.pvalue:.4f}")
    results["perspective_3_reset_residual"] = {"diff": float(np.mean(c0_s1)-np.mean(c0_s0)), "p": float(tt_ctrl.pvalue)}

    # -------------------------------------------------------------------------
    # PERSPECTIVE 4: QUBIT GEOMETRY / CROSSTALK (Middle Q49 conditioned on Q48 & Q50)
    # -------------------------------------------------------------------------
    print("\n--> 4. Geometric Crosstalk: Middle Q49 conditioned on Outer Q48 & Q50")
    # For zero_iq and zero_iq_energy_matched, qubits are [48, 49, 50] (pos 0, 1, 2)
    # Secret pattern: s_outer = (s[0] == s[2] == 1) vs (s[0] == s[2] == 0)
    outer_pat = df_moments.pivot_table(index=["family", "pair"], columns="qubit_pos", values=["secret_bit", "mean"])
    s0 = outer_pat["secret_bit"][0]
    s1 = outer_pat["secret_bit"][1]
    s2 = outer_pat["secret_bit"][2]
    u1 = outer_pat["mean"][1] # middle qubit centroid shift
    
    both_active = (s0 == 1) & (s2 == 1)
    both_passive = (s0 == 0) & (s2 == 0)
    u_active = u1[both_active].dropna()
    u_passive = u1[both_passive].dropna()
    
    if len(u_active) > 2 and len(u_passive) > 2:
        tt_geo = stats.ttest_ind(u_active, u_passive)
        diff_geo = float(np.mean(u_active) - np.mean(u_passive))
        print(f"    Q49 centroid diff when outer both 1 vs both 0: {diff_geo:+.6f} (n={len(u_active)},{len(u_passive)}) | p: {tt_geo.pvalue:.4f}")
        results["perspective_4_geometric_crosstalk"] = {"diff": diff_geo, "p": float(tt_geo.pvalue), "n_active": len(u_active), "n_passive": len(u_passive)}
    else:
        print("    Not enough samples in explore half.")

    # -------------------------------------------------------------------------
    # PERSPECTIVE 5: HAMMING WEIGHT DEPENDENCE IN SPACE_MEMORY & C_LIVE
    # -------------------------------------------------------------------------
    print("\n--> 5. Hamming Weight / Bit-String Parity Dependence")
    # In counts.parquet for c_live and space_memory
    sm = counts_df[counts_df.family.isin(["space_memory", "c_live", "c_live_simultaneous"])].copy()
    sm["hw"] = sm.bitstring.map(lambda b: sum(int(x) for x in str(b) if x in "01"))
    hw_by_arm = sm.groupby(["family", "arm"])["hw"].mean()
    print("    Mean Hamming Weight by Arm:")
    for (f, arm), val in hw_by_arm.items():
        print(f"      {f} | {arm}: {val:.4f}")
    results["perspective_5_hamming_weights"] = {f"{f}|{a}": float(v) for (f, a), v in hw_by_arm.items()}

    # -------------------------------------------------------------------------
    # PERSPECTIVE 6: SHOT-TO-SHOT MEMORY IN IQM GARNET (shot_memory.parquet)
    # -------------------------------------------------------------------------
    print("\n--> 6. Shot-to-Shot Autocorrelation (IQM Garnet shot_memory)")
    # For each job in mem_df, test autocorrelation of the first bit across shots
    lag1_corrs = []
    runs_pvals = []
    for job, g in mem_df.groupby("job_id"):
        bits = [int(b[0]) for b in g.sort_values("shot_index").bitstring.values if len(b) > 0]
        if len(bits) > 20 and len(set(bits)) > 1:
            # lag 1 autocorr
            r = np.corrcoef(bits[:-1], bits[1:])[0, 1]
            if not np.isnan(r):
                lag1_corrs.append(r)
            # Wald-Wolfowitz runs test
            n1 = sum(bits)
            n0 = len(bits) - n1
            if n0 > 0 and n1 > 0:
                runs = 1 + sum(bits[i] != bits[i+1] for i in range(len(bits)-1))
                mu = 1 + 2 * n0 * n1 / len(bits)
                var = (2 * n0 * n1 * (2 * n0 * n1 - len(bits))) / (len(bits)**2 * (len(bits) - 1))
                if var > 0:
                    z = (runs - mu) / np.sqrt(var)
                    runs_pvals.append(2 * stats.norm.sf(abs(z)))

    mean_r = float(np.mean(lag1_corrs)) if lag1_corrs else 0.0
    sig_runs = sum(p < 0.05 for p in runs_pvals) / len(runs_pvals) if runs_pvals else 0.0
    print(f"    Mean lag-1 autocorrelation: {mean_r:+.4f} (over {len(lag1_corrs)} jobs)")
    print(f"    Fraction of runs with Wald-Wolfowitz p < 0.05: {sig_runs:.2%} (expected 5.0%)")
    results["perspective_6_shot_memory"] = {"mean_lag1_corr": mean_r, "fraction_sig_runs": sig_runs, "n_jobs": len(lag1_corrs)}

    # -------------------------------------------------------------------------
    # PERSPECTIVE 7: CALIBRATION AGE / DRIFT OVER TIME
    # -------------------------------------------------------------------------
    print("\n--> 7. Temporal Drift / Time-Since-Calibration")
    # For zero_iq and c_live, check if pair order (pair index) shows monotonic drift
    iq_trend = df_moments.groupby("pair")["mean"].mean()
    tt_trend = stats.pearsonr(iq_trend.index, iq_trend.values)
    print(f"    zero_iq pair index vs centroid correlation: r = {tt_trend[0]:+.4f}, p = {tt_trend[1]:.4f}")
    results["perspective_7_temporal_drift"] = {"pearson_r": float(tt_trend[0]), "p": float(tt_trend[1])}

    # -------------------------------------------------------------------------
    # PERSPECTIVE 8: QPU VS RNG ENTROPY / BLOCK LENGTH
    # -------------------------------------------------------------------------
    print("\n--> 8. QPU vs PRNG Shannon Entropy & Distribution Balance")
    qpu_rng = counts_df[counts_df.family == "qpu_vs_rng"].copy()
    if len(qpu_rng) > 0:
        # Group by arm (QPU vs RNG)
        ent = {}
        for arm, g in qpu_rng.groupby("arm"):
            total_counts = g.groupby("bitstring")["count"].sum()
            probs = total_counts / total_counts.sum()
            entropy = -np.sum(probs * np.log2(probs + 1e-12))
            ent[arm] = float(entropy)
            print(f"      Arm {arm}: Shannon entropy = {entropy:.4f} bits (n_bitstrings={len(probs)})")
        results["perspective_8_entropy"] = ent

    # -------------------------------------------------------------------------
    # PERSPECTIVE 9: DELAY FINE STRUCTURE IN SPECTROSCOPY
    # -------------------------------------------------------------------------
    print("\n--> 9. Delay Fine Structure (spatial_bath_spectroscopy in explore)")
    sbs = counts_df[counts_df.family == "spatial_bath_spectroscopy"].copy()
    if len(sbs) > 0:
        print(f"    Spectroscopy entries in explore: {len(sbs)} rows across {sbs.job_id.nunique()} jobs")
        results["perspective_9_spectroscopy"] = {"n_rows": len(sbs), "n_jobs": int(sbs.job_id.nunique())}
    else:
        print("    spatial_bath_spectroscopy is in confirm half.")

    # -------------------------------------------------------------------------
    # PERSPECTIVE 10: SATELLITE PEAK FRACTION (OUTLIERS IN 0-CLOUD)
    # -------------------------------------------------------------------------
    print("\n--> 10. Thermal / Excited Satellite Fraction (>0.5 between 0 and 1)")
    # Fraction of shots falling in the intermediate regime u in [0.4, 0.8]
    main_iq["is_satellite"] = (main_iq["u"] >= 0.4) & (main_iq["u"] <= 0.8)
    sat = main_iq.groupby(["family", "pair", "qubit_pos", "secret_bit"])["is_satellite"].mean().reset_index()
    sat_s0 = sat[sat.secret_bit == 0]["is_satellite"]
    sat_s1 = sat[sat.secret_bit == 1]["is_satellite"]
    tt_sat = stats.ttest_ind(sat_s1, sat_s0)
    diff_sat = float(np.mean(sat_s1) - np.mean(sat_s0))
    print(f"    Satellite fraction diff (s1 - s0): {diff_sat:+.6f} (s0={np.mean(sat_s0):.4f}, s1={np.mean(sat_s1):.4f}) | p: {tt_sat.pvalue:.4f}")
    results["perspective_10_satellite_fraction"] = {"diff": diff_sat, "p": float(tt_sat.pvalue)}

    # Save summary
    out_json = HERE / "explore_ten_perspectives_summary.json"
    out_json.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("\n=====================================================================")
    print(f"EXPLORATION COMPLETE. Summary written to {out_json}")
    print("=====================================================================")

if __name__ == "__main__":
    run_all()
