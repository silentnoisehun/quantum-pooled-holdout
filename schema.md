# Unified Quantum Hardware Dataset Schema

## Files Overview

The consolidated dataset is partitioned into tabular format:

1. `counts.parquet` (or `counts.jsonl`):
   - `repo`: Origin repository name (e.g. `qhf-bell-spectator`, `quantum-space-memory`)
   - `campaign`: Campaign identifier or timestamp
   - `job_id`: IBM / IQM execution job ID
   - `backend`: Physical processor (`ibm_marrakesh`, `ibm_kingston`, `ibm_fez`, `iqm_garnet`)
   - `timestamp_utc`: Execution timestamp
   - `unit_id`: Stratification unit (pair / block / replicate)
   - `split`: Partition assignment (`explore` vs `confirm`)
   - `circuit_name`: Name or role of circuit (`main`, `cal0`, `cal1`, `ctrl_u0`, `ctrl_u1`, etc.)
   - `qubits`: List of physical qubits involved
   - `shots`: Number of shots executed
   - `counts`: Dictionary of measured bitstring counts
   - `is_duplicate`: Boolean flag (True for mirrored / duplicate entries)

2. `iq_shots.parquet` (or `.npz` archive):
   - Continuous complex analog IQ voltages for the 160 Kingston jobs in `zero_iq` and `zero_iq_energy_matched`.
   - Fields: `pair`, `circuit`, `qubit`, `shot_idx`, `I_val`, `Q_val`.

3. `metadata.json`:
   - Processor calibration properties, queue times, and ambient timestamps.
