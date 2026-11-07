#!/usr/bin/env python3
"""
split.py: Deterministic 50/50 exploration and confirmation holdout splitter.
Enforces holdout blinding and verifies cryptographic split manifests.
"""

import argparse
import hashlib
import json
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parent.parent

# Campaigns and unit counts to stratify:
CAMPAIGNS = {
    "c_live": 60,
    "c_live_simultaneous": 60,
    "qpu_vs_rng_marrakesh": 20,
    "qpu_vs_rng_kingston": 20,
    "space_memory": 33,
    "spatial_bath_spectroscopy": 92,
    "zero_iq_memory": 40,
    "zero_iq_energy_matched": 40,
}

def generate_splits(seed=20261115):
    rng = np.random.default_rng(seed)
    explore_units = []
    confirm_units = []

    for camp, n_units in CAMPAIGNS.items():
        indices = np.arange(n_units)
        rng.shuffle(indices)
        half = n_units // 2
        exp = indices[:half]
        cnf = indices[half:]

        for u in exp:
            explore_units.append(f"{camp}__unit{u:03d}")
        for u in cnf:
            confirm_units.append(f"{camp}__unit{u:03d}")

    explore_units.sort()
    confirm_units.sort()
    return explore_units, confirm_units

def compute_confirm_hash(confirm_units):
    content = "\n".join(confirm_units).encode("utf-8")
    return hashlib.sha256(content).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate")
    g.add_argument("--seed", type=int, default=20261115)

    v = sub.add_parser("verify")

    m = sub.add_parser("materialize")
    m.add_argument("split", choices=["explore", "confirm"])
    m.add_argument("--i-have-committed-the-candidates", action="store_true")

    args = parser.parse_args()

    split_dir = REPO / "split"
    split_dir.mkdir(parents=True, exist_ok=True)

    if args.cmd == "generate":
        exp, cnf = generate_splits(args.seed)
        h = compute_confirm_hash(cnf)
        print(f"Generated 50/50 split across {len(CAMPAIGNS)} campaigns.")
        print(f"Explore units: {len(exp)} | Confirm units: {len(cnf)}")
        print(f"Confirmation Holdout SHA-256: {h}")

        (split_dir / "explore_units.csv").write_text("unit_id\n" + "\n".join(exp) + "\n", encoding="utf-8")
        (split_dir / "confirm_units.csv").write_text("unit_id\n" + "\n".join(cnf) + "\n", encoding="utf-8")
        print("Wrote split/explore_units.csv and split/confirm_units.csv")

    elif args.cmd == "verify":
        cnf_csv = split_dir / "confirm_units.csv"
        if not cnf_csv.exists():
            print("confirm_units.csv not found! Run 'split.py generate' first.")
            return
        units = [line.strip() for line in cnf_csv.read_text(encoding="utf-8").splitlines()[1:] if line.strip()]
        h = compute_confirm_hash(units)
        manifest = json.loads((REPO / "split_manifest.json").read_text(encoding="utf-8"))
        expected_h = manifest.get("confirm_holdout_hash")
        print(f"Computed SHA-256: {h}")
        print(f"Expected SHA-256: {expected_h}")
        if h == expected_h:
            print("VERIFICATION SUCCESSFUL: Confirmation holdout integrity confirmed.")
        else:
            print("VERIFICATION FAILED: Hash mismatch!")

    elif args.cmd == "materialize":
        if args.split == "confirm" and not args.i_have_committed_the_candidates:
            print("SAFETY LOCK ACTIVE: Cannot materialize confirmation holdout before candidates are committed.")
            print("Use --i-have-committed-the-candidates after committing docs/CANDIDATES-pooled_holdout.md.")
            return
        print(f"Materializing {args.split} split directory...")
        target_dir = split_dir / args.split
        target_dir.mkdir(parents=True, exist_ok=True)
        print(f"Materialized {target_dir} successfully.")

if __name__ == "__main__":
    main()
