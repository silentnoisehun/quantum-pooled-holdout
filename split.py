#!/usr/bin/env python3
"""
split.py: deterministic exploration / confirmation split of every real hardware measurement.
Preregistration: docs/PREREGISTRATION-pooled_holdout.md

  python split.py manifest                 -> split_manifest.json + split/explore_units.csv + split/confirm_units.csv
  python split.py materialize explore      -> split/explore/ (the half you may search freely)
  python split.py materialize confirm      -> ONLY after the candidate rules are committed (see the preregistration)
  python split.py verify                   -> recomputes everything and checks it against split_manifest.json

Rules (fixed here, before anyone looks at a result):
  * Only data_class == hardware, not a duplicate copy, with a job id. Dry runs, simulations, the classical RNG
    arm on its own, histograms without a job id and zero-shot jobs are outside both halves.
    (The classical RNG arm of qpu_vs_rng shares its unit with the QPU arm of the same job and travels with it.)
  * The unit is never a shot. It is:
      - zero_iq, zero_iq_energy_matched, space_memory: one A+B pair            (campaign, pair)
      - c_live, c_live_simultaneous: one F+N block     (campaign, block)
      - loop, closed_loop, qpu_vs_rng (sequential feedback campaigns): 5 consecutive iterations (campaign, iter//5)
      - everything else: one job                        (job_id)
  * Stratum = (repo-independent family, campaign, unit arm). The unit arm is the arm label if every
    result in the unit has the same one, the secret-bit pattern for A+B pairs, otherwise "mixed".
  * Inside a stratum, units are ordered by SHA-256(seed | unit_id). The first floor(n/2) go to explore,
    the next floor(n/2) to confirm; an odd last unit goes by the lowest bit of its hash.
    No random-number library is used, so the split does not depend on numpy/python versions.
  * The values of the measurements are never read while splitting.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import pandas as pd

SEED = "pooled-holdout|silentnoisehun|2026-11-07|seed=20261107"
HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
REPOS = HERE / "repos"
OUT = HERE / "split"
BLOCK_FAMILIES = {"c_live", "c_live_simultaneous"}
PAIR_FAMILIES = {"space_memory", "zero_iq", "zero_iq_energy_matched"}
SEQ_FAMILIES = {"loop", "closed_loop", "qpu_vs_rng"}
SEQ_BLOCK = 5


def h(s):
    return hashlib.sha256(s.encode()).hexdigest()


def file_sha(rel):
    p = REPOS / rel
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def ctx_get(js, key):
    try:
        return json.loads(js).get(key)
    except Exception:
        return None


def unit_table():
    c = pd.read_parquet(DATA / "counts.parquet")
    keep = c[(~c.is_duplicate) & c.job_id.notna() & c.data_class.isin(["hardware", "classical_rng"])].copy()
    # results, not bitstring rows
    res = keep.drop_duplicates(["source_file", "json_path"]).copy()
    fam = res.family.copy()
    pair = res.source_file.str.extract(r"pair(\d+)")[0]
    blk = res.context_json.map(lambda s: ctx_get(s, "block"))
    blk = blk.astype(object).where(blk.notna(), res.source_file.str.extract(r"blk(\d+)")[0])
    it = res.source_file.str.extract(r"iter(\d+)")[0].astype(float)
    it = it.fillna(res.iteration)
    uid = []
    for f, camp, j, p, b, i, repo in zip(fam, res.campaign, res.job_id, pair, blk, it, res.repo):
        if f in PAIR_FAMILIES and pd.notna(p):
            uid.append(f"{f}|{camp}|pair{int(p):03d}")
        elif f in BLOCK_FAMILIES and pd.notna(b):
            uid.append(f"{f}|{camp}|block{int(float(b)):03d}")
        elif f in SEQ_FAMILIES and pd.notna(i):
            uid.append(f"{repo}|{f}|{camp}|iters{int(i) // SEQ_BLOCK * SEQ_BLOCK:04d}-{int(i) // SEQ_BLOCK * SEQ_BLOCK + SEQ_BLOCK - 1:04d}")
        else:
            uid.append(f"job|{j}")
    res["unit_id"] = uid
    # IQ shots of the zero_iq hardware campaign
    iq = pd.read_parquet(DATA / "iq_shots.parquet", columns=["family", "campaign", "pair", "job_id", "job_role", "data_class", "source_file", "secret_bit", "qubit_pos"])
    iq = iq[iq.data_class == "hardware"]
    iqu = iq.drop_duplicates(["campaign", "pair", "job_id"])[["family", "campaign", "pair", "job_id", "job_role", "source_file"]].copy()
    iqu["unit_id"] = [f"{f}|{c}|pair{int(p):03d}" for f, c, p in zip(iqu.family, iqu.campaign, iqu.pair)]
    bits = iq.drop_duplicates(["family", "campaign", "pair", "qubit_pos"]).sort_values("qubit_pos").groupby(["family", "campaign", "pair"]).secret_bit.agg(lambda s: "".join(map(str, s)))
    # arms per unit
    arms = {}
    for u, g in res.groupby("unit_id"):
        if u.startswith(("space_memory|",)):
            sb = g.context_json.map(lambda s: ctx_get(s, "secret_bits")).dropna()
            arms[u] = "s=" + "".join(map(str, sb.iloc[0])) if len(sb) else "mixed"
        else:
            a = set(g.arm.fillna("none"))
            arms[u] = a.pop() if len(a) == 1 else "mixed"
    for (f, c, p), b in bits.items():
        arms[f"{f}|{c}|pair{int(p):03d}"] = "s=" + b
    units = []
    for u, g in res.groupby("unit_id"):
        units.append({"unit_id": u, "family": g.family.iloc[0], "campaign": g.campaign.iloc[0],
                      "repos": ";".join(sorted(set(g.repo))), "job_ids": ";".join(sorted(set(g.job_id))),
                      "n_results": len(g), "arm": arms[u],
                      "files": sorted(set(g.source_file))})
    for u, g in iqu.groupby("unit_id"):
        units.append({"unit_id": u, "family": g.family.iloc[0], "campaign": g.campaign.iloc[0], "repos": "quantum-space-memory",
                      "job_ids": ";".join(sorted(set(g.job_id.dropna()))), "n_results": len(g), "arm": arms[u],
                      "files": sorted(set(g.source_file) | {re.sub(r"\.npz$", ".json", f) for f in g.source_file})})
    U = pd.DataFrame(units)
    U["stratum"] = U.family + "|" + U.campaign.astype(str) + "|" + U.arm.astype(str)
    return U, res


def assign(U):
    U = U.copy()
    U["key"] = [h(f"{SEED}|{u}") for u in U.unit_id]
    U = U.sort_values(["stratum", "key"]).reset_index(drop=True)
    half = []
    for s, g in U.groupby("stratum", sort=True):
        n = len(g)
        k = n // 2
        lab = ["explore"] * k + ["confirm"] * k
        if n % 2:
            lab.append("explore" if int(g.key.iloc[-1][-1], 16) % 2 == 0 else "confirm")
        half += lab
    U["half"] = half
    return U


def half_digest(U, half):
    """SHA-256 over the sorted list of (unit, job ids, file, sha256 of the file bytes). Reproducible from the repos."""
    lines = []
    for _, r in U[U.half == half].sort_values("unit_id").iterrows():
        for f in r.files:
            lines.append(f"{r.unit_id}\t{r.job_ids}\t{f}\t{file_sha(f)}")
    return h("\n".join(lines)), len(lines)


def ids_digest(U, half):
    return h("\n".join(sorted(U[U.half == half].unit_id)))


def build():
    U, res = unit_table()
    U = assign(U)
    return U, res


def manifest():
    U, res = build()
    OUT.mkdir(exist_ok=True)
    for half in ("explore", "confirm"):
        u = U[U.half == half].sort_values("unit_id")
        u.assign(files=u.files.map(lambda x: ";".join(x))).drop(columns=["key"]).to_csv(OUT / f"{half}_units.csv", index=False)
    d_e, n_e = half_digest(U, "explore")
    d_c, n_c = half_digest(U, "confirm")
    strat = U.groupby(["family", "half"]).size().unstack(fill_value=0)
    commits = {}
    for r in sorted(p.name for p in REPOS.iterdir() if p.is_dir()):
        head = (REPOS / r / ".git" / "HEAD").read_text().strip()
        ref = head.split(" ", 1)[1] if head.startswith("ref:") else None
        sha = (REPOS / r / ".git" / ref).read_text().strip() if ref and (REPOS / r / ".git" / ref).exists() else head
        if ref and not (REPOS / r / ".git" / ref).exists():
            pr = (REPOS / r / ".git" / "packed-refs")
            if pr.exists():
                for line in pr.read_text().splitlines():
                    if line.endswith(ref):
                        sha = line.split()[0]
        commits[r] = sha
    m = {
        "preregistration": "docs/PREREGISTRATION-pooled_holdout.md",
        "seed": SEED,
        "rule": "stratum=(family,campaign,unit arm); order by sha256(seed|unit_id); first floor(n/2) explore, next floor(n/2) confirm; odd last unit by lowest hash bit",
        "source_repos_at_commit": commits,
        "n_units": {"explore": int((U.half == "explore").sum()), "confirm": int((U.half == "confirm").sum())},
        "n_jobs": {hf: int(len(set(";".join(U[U.half == hf].job_ids).split(";")) - {""})) for hf in ("explore", "confirm")},
        "units_per_family": {f: {k: int(v) for k, v in row.items()} for f, row in strat.iterrows()},
        "sha256_unit_ids": {"explore": ids_digest(U, "explore"), "confirm": ids_digest(U, "confirm")},
        "sha256_half_content": {"explore": d_e, "confirm": d_c,
                                "definition": "sha256 of newline-joined sorted lines 'unit_id<TAB>job_ids<TAB>file<TAB>sha256(file bytes)'",
                                "lines": {"explore": n_e, "confirm": n_c}},
        "explore_units": sorted(U[U.half == "explore"].unit_id),
        "confirm_units": sorted(U[U.half == "confirm"].unit_id),
        "explore_job_ids": sorted(set(";".join(U[U.half == "explore"].job_ids).split(";")) - {""}),
        "confirm_job_ids": sorted(set(";".join(U[U.half == "confirm"].job_ids).split(";")) - {""}),
    }
    (HERE / "split_manifest.json").write_text(json.dumps(m, indent=1), encoding="utf-8")
    print(json.dumps({k: m[k] for k in ("n_units", "n_jobs", "sha256_unit_ids", "sha256_half_content")}, indent=1))
    print(strat)


def materialize(half):
    if half == "confirm" and "--i-have-committed-the-candidates" not in sys.argv:
        sys.exit("The confirmation half opens only after the candidate rules are committed and pushed. "
                 "Re-run with --i-have-committed-the-candidates once that commit exists.")
    U, res = build()
    m = json.loads((HERE / "split_manifest.json").read_text(encoding="utf-8"))
    if ids_digest(U, half) != m["sha256_unit_ids"][half]:
        sys.exit("Unit list differs from split_manifest.json: refusing.")
    units = set(U[U.half == half].unit_id)
    d = OUT / half
    d.mkdir(parents=True, exist_ok=True)
    c = pd.read_parquet(DATA / "counts.parquet")
    c = c.merge(res[["source_file", "json_path", "unit_id"]], on=["source_file", "json_path"], how="inner")
    c[c.unit_id.isin(units)].to_parquet(d / "counts.parquet", index=False)
    iq = pd.read_parquet(DATA / "iq_shots.parquet")
    iq = iq[iq.data_class == "hardware"].copy()
    iq["unit_id"] = [f"{f}|{a}|pair{int(p):03d}" for f, a, p in zip(iq.family, iq.campaign, iq.pair)]
    iq[iq.unit_id.isin(units)].to_parquet(d / "iq_shots.parquet", index=False)
    mem = pd.read_parquet(DATA / "shot_memory.parquet")
    mem = mem[mem.job_id.isin(set(";".join(U[U.half == half].job_ids).split(";")))]
    mem.to_parquet(d / "shot_memory.parquet", index=False)
    print(f"{half}: {len(units)} units written to {d}")


def verify():
    U, _ = build()
    m = json.loads((HERE / "split_manifest.json").read_text(encoding="utf-8"))
    ok = True
    for half in ("explore", "confirm"):
        a = ids_digest(U, half) == m["sha256_unit_ids"][half]
        b = half_digest(U, half)[0] == m["sha256_half_content"][half]
        print(half, "unit ids", "OK" if a else "MISMATCH", "| content", "OK" if b else "MISMATCH")
        ok &= a and b
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "manifest"
    if cmd == "manifest":
        manifest()
    elif cmd == "materialize":
        materialize(sys.argv[2])
    elif cmd == "verify":
        verify()
    else:
        sys.exit(__doc__)
