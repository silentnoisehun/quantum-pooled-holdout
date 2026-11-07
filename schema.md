# Pooled quantum measurement table: schema

Built by `build_dataset.py` from the ten public repositories of silentnoisehun (GitHub), cloned on 2026-11-07 at the commits listed in `split_manifest.json` (`source_repos_at_commit`). Nothing in these files is analysed; they are a lossless re-arrangement of what the repos contain.

## Files

| File | One row is | Rows |
|---|---|---|
| `data/counts.parquet` (and `counts.csv.gz`) | one bitstring of one counts histogram | 68,650 |
| `data/iq_shots.parquet` | one shot of one qubit, raw IQ point (zero_iq and zero_iq_energy_matched) | 3,932,160 |
| `data/shot_memory.parquet` | one shot, in order, from a per-shot `memory` list (IQM Garnet, quantum-anchor) | 13,322 |
| `data/empty_jobs.csv` | one result that came back with zero shots (IQM Garnet) | 16 |
| `data/files_inventory.csv` | one file seen, and what was extracted from it | all JSON/NPZ files |

## counts.parquet

| Column | Meaning |
|---|---|
| `row_id` | running index |
| `repo` | repository name |
| `source_file` | path of the JSON file, `repo/...` |
| `json_path` | where in the file the histogram sits; together with `source_file` it identifies one result |
| `family` | experiment family (folder under `measurement_raw/`, or the file stem without timestamps and job ids) |
| `campaign` | campaign folder or timestamp |
| `data_class` | `hardware` (job id present), `hardware_no_job_id`, `classical_rng` (arm C of qpu_vs_rng, rebuilt marginals), `dry_run`, `simulation`, `unknown`. Only `hardware` enters any real analysis or the split |
| `job_id`, `job_id_source` | IBM or IQM job id; source is `context` (same JSON object), `inferred_from_script` (space_memory controls run inside job B), `matched_identical_histogram` (summary file without id, byte-identical to one tagged histogram), `same_iteration_file` |
| `backend` | ibm_marrakesh, ibm_kingston, ibm_fez, garnet; empty where the file does not say |
| `physical_qubits` | JSON list of physical qubits as recorded (layout, `physical_qubits`, `qubits`); empty where the script let the transpiler choose and did not save the layout |
| `arm` | arm, condition or circuit label (F/N, arm_Q/arm_C, main/cal0/ctrl_u1, s=..., protocol name) |
| `register` | key of the histogram (`counts`, `c1`, `c2`, `marginal_q0`...) |
| `iteration` | iteration, pair, block or replicate number where recorded |
| `params` | JSON of numeric parameters found in the enclosing objects (theta, angle, phi, tau_us, f, A, ...) |
| `bitstring`, `n_bits`, `count` | the outcome and its count; bitstrings are Qiskit order (rightmost = classical bit 0), spaces between registers removed |
| `counts_total`, `shots_declared`, `counts_partial` | sum of the histogram, the declared shots, and whether the histogram has fewer shots than declared |
| `timestamp`, `timestamp_source`, `time_utc` | as found (`json` or `filename`), and normalised to UTC |
| `calibration_timestamp`, `calibration_utc` | backend properties timestamp where the run saved one |
| `result_key` | hash of job id + exact histogram (+ its occurrence number in the file); the same result copied into several files has the same key |
| `is_duplicate`, `copies` | `True` on every copy except the canonical one (per-run file preferred over summaries); number of files holding it. Use `is_duplicate == False` |
| `context_json` | every scalar of the enclosing objects, for anything the columns above missed |

## iq_shots.parquet

`repo, family, campaign, data_class, backend, pair, job_role (A/B), job_id, circuit (A, main, cal0, cal1, ctrl_u0, ctrl_u1), register (c, c1, c2), shot_index (order within the circuit as returned), qubit_pos (0-2), physical_qubit, secret_bit, I, Q, source_file, calibration_timestamp`.

## Coverage of the hardware results (unique, `is_duplicate == False`)

3,874 results from 856 jobs, 5.11 million shots, 2026-10-07 to 2026-11-07, on ibm_marrakesh, ibm_kingston, ibm_fez and IQM Garnet; plus 1.97 million IQ shot-points from 160 Kingston jobs.

| Field | Filled |
|---|---|
| backend | 94% (missing: qhf-core closed_loop, part of quantum-anchor, wave-quantum fez runs 1-3) |
| physical qubits | 61% (qhf-core 19%, quantum-hydrodynamic-feedback 0%, quantum-anchor 2%, wave-quantum 24%) |
| arm or label | 90% |
| angle or parameter | 18% (most circuits encode the parameter in the circuit only, not in the JSON) |
| time | 90% |
| calibration timestamp | 50% (only the November 7 campaigns save it) |

## What could not be unified

- **Shot order.** Counts histograms throw it away. Shot order exists only in the zero_iq IQ data and in the IQM `memory` lists.
- **Encoded parameters.** In quantum-hydrodynamic-feedback, qhf-core loop/closed_loop and wave-quantum the angle fed to each circuit is computed from the fluid state at run time and only partly saved; where it is not in the JSON, `params` is empty.
- **Physical qubits** were not saved where the transpiler chose the layout (see table).
- **quantum-anchored-memory**: 4 histograms without job id and 10 of unknown origin; excluded. The known job-id mismatch for the 99.41% result is not repaired here.
- **scs-quantum** contains no measurement data (only a CI log); **qhf-topological-vortex** contains only a README.
- **memory_decay_sweep** stores only P(1) per qubit with the shot count; marginal counts were rebuilt as round(P1 x shots).
- **qpu_vs_rng arm C** is a classical RNG: stored as sampled per-qubit marginals, class `classical_rng`.
- **Sixteen IQM Garnet results returned zero shots** (`empty_jobs.csv`): kept as a list, not as counts.
- **Duplicates:** 7,364 of 16,580 extracted results are copies (qhf-core holds copies of most qhf-bell-spectator folders; summary files repeat per-run files).

## Excluded from every real analysis

`data_class` in `dry_run` (871 results and 1.97 million IQ points), `simulation` (77), `classical_rng` on its own, `hardware_no_job_id`, `unknown`, and every `is_duplicate == True` row.
