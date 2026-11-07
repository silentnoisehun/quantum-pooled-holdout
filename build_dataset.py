#!/usr/bin/env python3
"""
build_dataset.py: every quantum measurement from silentnoisehun's public repos in one table.

Outputs (in ./data):
  counts.parquet / counts.csv.gz  one row per (circuit result, register, bitstring) count
  iq_shots.parquet               one row per single shot, per qubit, raw IQ point (zero_iq campaigns)
  files_inventory.csv            every data file seen, with what was extracted from it and why not

Usage:
  python build_dataset.py --repos ./repos        (repos cloned from api.github.com/users/silentnoisehun/repos)

The extractor is generic: it walks every JSON file, finds every dict whose keys are bitstrings
and whose values are integers (a counts histogram), and attaches the scalar context of every
enclosing dict (job id, backend, qubits, arm, angle, timestamps...). Nothing is analysed here.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

BIT_RE = re.compile(r"^[01]+( [01]+)*$")
IBM_JOB_RE = re.compile(r"^[cd][a-z0-9]{19}$")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
TS_RE = re.compile(r"(20\d{6}T\d{4,6}Z?)")
DATA_DIR_HINTS = ("measurement_raw", "results", "data", "raw")
SKIP_NAMES = {".zenodo.json", "package.json", "package-lock.json", "tsconfig.json", "CITATION.cff"}

JOB_KEYS = ("job_id", "jobid", "job", "ibm_job_id", "iqm_job_id")
BACKEND_KEYS = ("backend", "backend_name", "device", "qpu")
QUBIT_KEYS = ("physical_qubits", "physical_qubit", "qubits", "qubit", "initial_layout", "layout")
ARM_KEYS = ("arm", "condition", "state", "prep", "label", "mode", "protocol", "variant", "kind", "name", "circuit", "type")
PARAM_KEYS = ("theta", "angle", "angle_deg", "phi", "lam", "tau_us", "tau", "delay_us", "delay", "t_us", "f", "A",
              "band", "k", "n", "detuning", "freq", "step", "depth", "reps", "amp", "strength", "g")
TIME_KEYS = ("timestamp_utc", "submitted_utc", "t_submit", "start_utc", "created_utc", "created", "time_utc", "timestamp", "date")
CAL_KEYS = ("calibration_start", "calibration_timestamp", "calibration_utc", "cal_last_update", "last_update_date",
            "properties_last_update", "calibration")
ITER_KEYS = ("iteration", "iter", "pair", "block", "replicate", "run", "rep")
SIM_RE = re.compile(r"(^|[/_\-.])(dry|dryrun|sim|simulated|simulation|statevector|aer|local|noise_model|noisemodel|fake|replay|mock)([/_\-.]|$)")


def is_counts(d):
    if not isinstance(d, dict) or not d:
        return False
    for k, v in d.items():
        if not isinstance(k, str) or not BIT_RE.match(k):
            return False
        if isinstance(v, bool) or not isinstance(v, (int, np.integer)) and not (isinstance(v, float) and float(v).is_integer()):
            return False
    return True


def scalar(v):
    return isinstance(v, (str, int, float, bool)) or v is None


def short_list(v):
    return isinstance(v, list) and len(v) <= 64 and all(isinstance(x, (int, float, str)) for x in v)


def walk(o, ctx, path, out):
    """Collect (counts, context, path) for every counts dict."""
    if isinstance(o, dict):
        if is_counts(o):
            out.append((o, dict(ctx), path))
            return
        local = dict(ctx)
        for k, v in o.items():
            if scalar(v) or short_list(v):
                local[k] = v
        for k, v in o.items():
            if isinstance(v, (dict, list)) and not short_list(v):
                c2 = dict(local)
                c2.setdefault("_keys", [])
                c2["_keys"] = list(c2["_keys"]) + [k]
                walk(v, c2, path + "/" + str(k), out)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            if isinstance(v, (dict, list)):
                c2 = dict(ctx)
                c2["_idx"] = list(ctx.get("_idx", [])) + [i]
                walk(v, c2, f"{path}[{i}]", out)


def pick(ctx, keys, test=None):
    for k in keys:
        if k in ctx and ctx[k] not in (None, ""):
            if test is None or test(ctx[k]):
                return ctx[k]
    return None


def find_job(ctx):
    for k in JOB_KEYS:
        v = ctx.get(k)
        if isinstance(v, str) and (IBM_JOB_RE.match(v) or UUID_RE.match(v)):
            return v
    for k, v in ctx.items():
        if isinstance(v, str) and ("job" in k.lower()) and (IBM_JOB_RE.match(v) or UUID_RE.match(v)):
            return v
    return None


def family_and_campaign(rel):
    parts = rel.split("/")
    fname = parts[-1]
    if "measurement_raw" in parts:
        i = parts.index("measurement_raw")
        sub = parts[i + 1:-1]
        if len(sub) >= 2:
            return sub[0], sub[1]
        if len(sub) == 1:
            return sub[0], sub[0]
    stem = fname.rsplit(".", 1)[0]
    m = TS_RE.search(stem)
    fam = re.sub(r"(_?20\d{6}T\d{4,6}Z?.*$)|(_d[a-z0-9]{19}.*$)|(_iter\d+.*$)", "", stem)
    fam = re.sub(r"_?[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "", fam)
    fam = re.sub(r"_01a1[0-9a-f]{4}", "", fam)
    fam = re.sub(r"_\d+s$", "", fam) or stem
    camp = m.group(1) if m else stem
    return fam, camp


def classify(rel, ctx, backend, job):
    low = rel.lower()
    blob = (low + " " + json.dumps({k: v for k, v in ctx.items() if isinstance(v, (str, bool))}, default=str).lower())
    if ctx.get("dry_run") is True or "dry" in low:
        return "dry_run"
    if SIM_RE.search(low) or (isinstance(backend, str) and any(m in backend.lower() for m in ("aer", "sim", "statevector", "fake", "local"))):
        return "simulation"
    if job is not None:
        return "hardware"
    if isinstance(backend, str) and re.match(r"^(ibm_|iqm|garnet|emerald|sirius|wukong|origin)", backend.lower()):
        return "hardware_no_job_id"
    if re.search(r"\b(simulat\w*|statevector|ideal)\b", blob):
        return "simulation"
    return "unknown"


def jdump(v):
    return None if v is None else json.dumps(v, default=str, sort_keys=True)


def extract_json(path, repo_root, repo):
    rel = f"{repo}/" + str(path.relative_to(repo_root))
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return [], {"file": rel, "status": "unreadable", "note": str(e)[:120]}
    base = {}
    cj = path.parent / "campaign.json"
    if cj.exists() and cj != path:
        try:
            c = json.loads(cj.read_text(encoding="utf-8"))
            base = {k: v for k, v in c.items() if (scalar(v) or short_list(v)) and not (isinstance(v, str) and len(v) > 200)}
            if "layout" in c and isinstance(c["layout"], (list, dict)):
                base["layout"] = c["layout"] if short_list(c["layout"]) else json.dumps(c["layout"])[:200]
        except Exception:
            pass
    found = []
    walk(obj, base, "", found)
    fam, camp = family_and_campaign(rel)
    rows = []
    for counts, ctx, jpath in found:
        job = find_job(ctx)
        job_src = "context" if job else None
        if job is None and jpath.startswith("/controls") and isinstance(obj, dict) and isinstance(obj.get("B"), dict):
            job = obj["B"].get("job_id")  # space_memory: controls run inside job B (scripts/space_memory.py)
            job_src = "inferred_from_script"
        backend = pick(ctx, BACKEND_KEYS, lambda v: isinstance(v, str))
        qubits = pick(ctx, QUBIT_KEYS)
        arm = None
        keys = ctx.get("_keys", [])
        arm_ctx = pick(ctx, ARM_KEYS, lambda v: isinstance(v, (str, int)) and not isinstance(v, bool))
        # the name of the enclosing key is often the arm ("arm_Q", "F", "main", "ctrl_u1")
        enclosing = [k for k in keys if k not in ("counts", "counts_raw", "counts_normalized", "data", "results", "points", "rows", "replicates")]
        arm = arm_ctx if arm_ctx is not None else (enclosing[-1] if enclosing else None)
        register = keys[-1] if keys else "counts"
        params = {k: ctx[k] for k in PARAM_KEYS if k in ctx and isinstance(ctx[k], (int, float)) and not isinstance(ctx[k], bool)}
        it = pick(ctx, ITER_KEYS, lambda v: isinstance(v, (int, float)) and not isinstance(v, bool))
        ts = pick(ctx, TIME_KEYS, lambda v: isinstance(v, (str, int, float)) and not isinstance(v, bool))
        cal = pick(ctx, CAL_KEYS, lambda v: isinstance(v, (str, int, float)) and not isinstance(v, bool))
        if isinstance(ts, (int, float)) and ts > 1e9:
            ts = pd.Timestamp(ts, unit="s", tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
        if ts is None:
            m = TS_RE.search(rel)
            ts = m.group(1) if m else None
            ts_src = "filename" if m else None
        else:
            ts_src = "json"
        cls = classify(rel, ctx, backend, job)
        total = int(sum(int(v) for v in counts.values()))
        shots_decl = ctx.get("shots") if isinstance(ctx.get("shots"), int) else None
        ctx_clean = {k: v for k, v in ctx.items() if not k.startswith("_") and (scalar(v) or short_list(v)) and not (isinstance(v, str) and len(v) > 200)}
        canon = json.dumps(sorted((k, int(v)) for k, v in counts.items()))
        fp = hashlib.sha1(f"{job}|{canon}|{jdump(params)}|{arm}|{register}|{jdump(ctx.get('_idx'))}".encode()).hexdigest()[:16]
        for b, c in counts.items():
            rows.append({
                "repo": repo, "source_file": rel, "json_path": jpath, "family": fam, "campaign": camp,
                "data_class": cls, "job_id": job, "job_id_source": job_src, "backend": backend, "physical_qubits": jdump(qubits),
                "arm": None if arm is None else str(arm), "register": register, "iteration": it,
                "params": jdump(params) if params else None, "bitstring": b.replace(" ", ""), "n_bits": len(b.replace(" ", "")),
                "count": int(c), "counts_total": total, "shots_declared": shots_decl,
                "counts_partial": bool(shots_decl is not None and total < shots_decl),
                "timestamp": None if ts is None else str(ts), "timestamp_source": ts_src,
                "calibration_timestamp": None if cal is None else str(cal),
                "result_fingerprint": fp, "context_json": json.dumps(ctx_clean, default=str, sort_keys=True)[:4000],
            })
    walk_extra(obj, {}, "", rel, repo)
    if "memory_decay_sweep" in rel and isinstance(obj, dict) and "sweep_data" in obj:
        rows += decay_sweep_rows(obj, rel, repo, fam, camp)
    inv = {"file": rel, "status": "counts_extracted" if rows else "no_counts", "n_count_blocks": len(found),
           "n_rows": len(rows), "family": fam, "campaign": camp}
    # classical RNG arm of qpu_vs_rng: sampled marginals, no bitstring histogram
    if "qpu_vs_rng" in rel and isinstance(obj, dict):
        reps = obj.get("replicates")
        for rep in (reps if isinstance(reps, list) else []):
            c = rep.get("arm_C", {})
            ks = c.get("k_sampled")
            if isinstance(ks, list):
                shots_c = obj.get("shots") if isinstance(obj.get("shots"), int) else None
                for qi, k in enumerate(ks):
                    rows.append({"repo": repo, "source_file": rel, "json_path": f"/replicates[{rep.get('replicate')}]/arm_C/k_sampled[{qi}]",
                                 "family": fam, "campaign": camp, "data_class": "classical_rng", "job_id": obj.get("job_id"), "job_id_source": "same_iteration_file",
                                 "backend": None, "physical_qubits": None, "arm": "arm_C", "register": f"marginal_q{qi}",
                                 "iteration": obj.get("iteration"), "params": jdump(c.get("fluid_params")), "bitstring": "1", "n_bits": 1,
                                 "count": int(k), "counts_total": shots_c, "shots_declared": shots_c, "counts_partial": False,
                                 "timestamp": None, "timestamp_source": None, "calibration_timestamp": None,
                                 "result_fingerprint": hashlib.sha1(f"{rel}{rep.get('replicate')}{qi}".encode()).hexdigest()[:16],
                                 "context_json": json.dumps({"replicate": rep.get("replicate")})})
    return rows, inv


MEM_ROWS, EMPTY_ROWS = [], []


def walk_extra(o, ctx, path, rel, repo):
    """Per-shot bitstring sequences ('memory' lists, IQM) and jobs that returned zero shots."""
    if isinstance(o, dict):
        local = dict(ctx)
        for k, v in o.items():
            if scalar(v):
                local[k] = v
        if o.get("returned_shots") == 0 or o.get("shot_loss") is True:
            EMPTY_ROWS.append({"repo": repo, "source_file": rel, "json_path": path, "job_id": find_job(local),
                               "backend": pick(local, BACKEND_KEYS, lambda v: isinstance(v, str)),
                               "label": pick(local, ARM_KEYS, lambda v: isinstance(v, str)),
                               "requested_shots": o.get("requested_shots", local.get("requested_shots")),
                               "returned_shots": o.get("returned_shots"), "shot_loss_pct": o.get("shot_loss_pct")})
        for k, v in o.items():
            if k == "memory" and isinstance(v, list) and v and all(isinstance(x, str) for x in v[:50]):
                job = find_job(local)
                for i, b in enumerate(v):
                    MEM_ROWS.append({"repo": repo, "source_file": rel, "json_path": f"{path}/memory", "job_id": job,
                                     "backend": pick(local, BACKEND_KEYS, lambda v: isinstance(v, str)),
                                     "label": pick(local, ARM_KEYS, lambda v: isinstance(v, str)),
                                     "shot_index": i, "bitstring": str(b).replace(" ", "")})
            elif isinstance(v, (dict, list)):
                walk_extra(v, local, f"{path}/{k}", rel, repo)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            if isinstance(v, (dict, list)):
                walk_extra(v, ctx, f"{path}[{i}]", rel, repo)


def decay_sweep_rows(obj, rel, repo, fam, camp):
    """memory_decay_sweep stores only per-qubit P(1) with known shots: rebuild marginal counts."""
    rows = []
    shots = obj.get("shots")
    q = obj.get("qubits")
    for pt in obj.get("sweep_data", []):
        for arm in ("p1_u0", "p1_u1"):
            for qi, p1 in enumerate(pt.get(arm, [])):
                k = int(round(p1 * shots))
                for b, c in (("1", k), ("0", shots - k)):
                    rows.append({"repo": repo, "source_file": rel, "json_path": f"/sweep_data[tau={pt.get('tau_us')}]/{arm}[{qi}]",
                                 "family": fam, "campaign": camp, "data_class": "hardware", "job_id": obj.get("job_id"),
                                 "job_id_source": "context", "backend": obj.get("backend"),
                                 "physical_qubits": json.dumps([q[qi]]) if q else None, "arm": arm.replace("p1_", ""),
                                 "register": f"marginal_q{qi}", "iteration": None, "params": json.dumps({"tau_us": pt.get("tau_us")}),
                                 "bitstring": b, "n_bits": 1, "count": c, "counts_total": shots, "shots_declared": shots,
                                 "counts_partial": False, "timestamp": None, "timestamp_source": None,
                                 "calibration_timestamp": obj.get("calibration_timestamp"),
                                 "result_fingerprint": hashlib.sha1(f"{rel}{arm}{qi}{pt.get('tau_us')}".encode()).hexdigest()[:16],
                                 "context_json": json.dumps({"rebuilt_from": "p1 x shots, rounded"})})
    return rows


def extract_iq(campdir, repo_root, repo):
    """zero_iq campaigns: one row per shot per qubit, raw complex IQ point."""
    rel_dir = f"{repo}/" + str(campdir.relative_to(repo_root))
    camp = json.loads((campdir / "campaign.json").read_text(encoding="utf-8"))
    phys = camp.get("physical_qubits")
    cls = "dry_run" if camp.get("dry_run") else "hardware"
    frames, invs = [], []
    for f in sorted(campdir.glob("pair*.npz")):
        meta = json.loads(f.with_suffix(".json").read_text(encoding="utf-8"))
        z = np.load(f)
        s = meta.get("secret_bits")
        for key in z.files:
            arr = np.asarray(z[key])
            role, _, rest = key.partition("__")
            circuit, _, reg = rest.rpartition("__") if rest.count("__") else ("A" if role == "A" else rest, "", rest)
            if role == "A":
                circuit, reg = "A", rest
            job = (meta.get(role) or {}).get("job_id") if isinstance(meta.get(role), dict) else None
            n, nq = arr.shape
            shot = np.repeat(np.arange(n), nq)
            qpos = np.tile(np.arange(nq), n)
            flat = arr.reshape(-1)
            frames.append(pd.DataFrame({
                "repo": repo, "family": campdir.parent.name, "campaign": camp.get("tag"), "data_class": cls, "backend": camp.get("backend"),
                "pair": meta.get("pair"), "job_role": role, "job_id": job, "circuit": circuit, "register": reg,
                "shot_index": shot.astype(np.int32), "qubit_pos": qpos.astype(np.int8),
                "physical_qubit": [phys[q] if phys else None for q in qpos],
                "secret_bit": [s[q] if s else None for q in qpos],
                "I": flat.real.astype(np.float32), "Q": flat.imag.astype(np.float32),
                "source_file": f"{rel_dir}/{f.name}",
                "calibration_timestamp": camp.get("calibration_start"),
            }))
        invs.append({"file": f"{rel_dir}/{f.name}", "status": "iq_extracted", "n_rows": int(sum(len(x) for x in frames[-len(z.files):]))})
    return frames, invs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repos", default="repos")
    ap.add_argument("--out", default="data")
    a = ap.parse_args()
    root = Path(a.repos)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rows, inv, iq = [], [], []
    for repo_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        repo = repo_dir.name
        for f in sorted(repo_dir.rglob("*")):
            if ".git" in f.parts or not f.is_file():
                continue
            if f.suffix == ".json" and f.name not in SKIP_NAMES:
                r, i = extract_json(f, repo_dir, repo)
                rows += r
                inv.append(i)
            elif f.suffix in (".csv", ".jsonl", ".npy", ".pkl", ".h5", ".txt") and any(h in f.parts for h in DATA_DIR_HINTS):
                inv.append({"file": f"{repo}/{f.relative_to(repo_dir)}", "status": "not_parsed", "note": f.suffix})
        for campdir in sorted(repo_dir.rglob("zero_iq*/*")):
            if campdir.is_dir() and (campdir / "campaign.json").exists() and list(campdir.glob("pair*.npz")):
                fr, iv = extract_iq(campdir, repo_dir, repo)
                iq += fr
                inv += iv
    df = pd.DataFrame(rows)
    # duplicates: the same result copied into several files (per-run file + aggregate file + summary,
    # and whole folders copied between qhf-core and qhf-bell-spectator). Key: job id + exact histogram
    # + the k-th occurrence of that pair inside the file (so two identical histograms of different
    # circuits in one job stay distinct). Without a job id: repo + histogram + params + k.
    blk = df.drop_duplicates(["source_file", "json_path"])[["source_file", "json_path", "job_id", "repo", "params"]].copy()
    canon = df.groupby(["source_file", "json_path"]).apply(
        lambda g: json.dumps(sorted(zip(g.bitstring, g["count"].astype(int)))), include_groups=False).rename("canon").reset_index()
    blk = blk.merge(canon, on=["source_file", "json_path"])
    # a histogram without a job id that is byte-identical to exactly one job-tagged histogram elsewhere
    # is a copy of it (summary files that dropped the job id): inherit the job id
    tagged = blk[blk.job_id.notna()].groupby("canon")["job_id"].agg(lambda s: sorted(set(s)))
    blk["job_inferred"] = [tagged[c][0] if (pd.isna(j) and c in tagged.index and len(tagged[c]) == 1 and len(json.loads(c)) > 2) else None
                           for j, c in zip(blk.job_id, blk.canon)]
    blk["job_id"] = blk.job_id.fillna(blk.job_inferred)
    blk["base"] = np.where(blk.job_id.notna(), blk.job_id.astype(str) + "|" + blk.canon,
                           blk.repo + "|" + blk.canon + "|" + blk.params.fillna(""))
    blk["k"] = blk.groupby(["source_file", "base"]).cumcount()
    blk["result_key"] = [hashlib.sha1(f"{b}|{k}".encode()).hexdigest()[:16] for b, k in zip(blk.base, blk.k)]
    # canonical copy: prefer per-run files over summaries/aggregates, then the alphabetically first file
    blk["is_agg"] = blk.source_file.str.contains(r"summary|all_runs|all_circuits|merge|_latest", regex=True)
    blk = blk.sort_values(["result_key", "is_agg", "source_file", "json_path"])
    blk["is_duplicate"] = blk.duplicated("result_key")
    blk["copies"] = blk.groupby("result_key")["source_file"].transform("nunique")
    df = df.drop(columns=["result_fingerprint"]).merge(blk[["source_file", "json_path", "result_key", "is_duplicate", "copies", "job_inferred"]],
                                                      on=["source_file", "json_path"], how="left")
    m = df.job_id.isna() & df.job_inferred.notna()
    df.loc[m, "job_id"] = df.loc[m, "job_inferred"]
    df.loc[m, "job_id_source"] = "matched_identical_histogram"
    df.loc[m & (df.data_class == "hardware_no_job_id"), "data_class"] = "hardware"
    df = df.drop(columns=["job_inferred"])
    def norm_time(v):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return None
        v = str(v)
        m = re.match(r"^(20\d{2})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})?Z?$", v)
        if m:
            y, mo, d, hh, mi, ss = m.groups()
            return f"{y}-{mo}-{d}T{hh}:{mi}:{ss or '00'}Z"
        try:
            t = pd.Timestamp(v)
            t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
            return t.strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            return None
    df["time_utc"] = df.timestamp.map(norm_time)
    df["calibration_utc"] = df.calibration_timestamp.map(norm_time)
    df = df.sort_values(["repo", "source_file", "json_path", "bitstring"]).reset_index(drop=True)
    df.insert(0, "row_id", np.arange(len(df)))
    df.to_parquet(out / "counts.parquet", index=False)
    df.to_csv(out / "counts.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    if iq:
        iqdf = pd.concat(iq, ignore_index=True)
        iqdf.to_parquet(out / "iq_shots.parquet", index=False)
    pd.DataFrame(inv).to_csv(out / "files_inventory.csv", index=False)
    pd.DataFrame(MEM_ROWS).to_parquet(out / "shot_memory.parquet", index=False)
    pd.DataFrame(EMPTY_ROWS).to_csv(out / "empty_jobs.csv", index=False)
    print("shot-memory rows:", len(MEM_ROWS), "| zero-shot results:", len(EMPTY_ROWS))
    print("count rows:", len(df), "| iq rows:", sum(len(x) for x in iq), "| files:", len(inv))
    print(df.groupby(["data_class"]).size())


if __name__ == "__main__":
    main()
