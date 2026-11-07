# Preregistration: pooled exploration / confirmation split of all hardware measurements

Author: Máté Róbert (ORCID 0009-0003-3986-6039)
Repository: https://github.com/silentnoisehun/quantum-pooled-holdout
Date of registration: 2026-11-07 10:30:00 UTC
Scripts: `build_dataset.py`, `split.py` (seed string `pooled-holdout|silentnoisehun|2026-11-07|seed=20261107`)

## Why

Ten repositories hold 1,016 hardware jobs with a job id (856 with counts histograms, 160 with raw IQ shots) (IBM Marrakesh, Kingston, Fez; IQM Garnet; October 7 to November 7, 2026). Every preregistered primary test so far has come out null. The author suspects that a real pattern sits in a variable nobody has looked at (state, angle, value, time, qubit, order). Searching all of that freely would find something by chance. This protocol allows the free search and still gives a clean test: search one half, confirm on the other.

## What was already seen (honest limits)

The aggregate primary results of every campaign are public and have been read by the author and by his assistant. The split protects against new fine-grained searches, not against ideas already inspired by those aggregates. A candidate that restates an already-reported aggregate effect is not eligible.

The two halves come from the same campaigns, the same days and the same qubits. A confirmation on the held-out half therefore shows that a pattern is reproducible within these runs, not that it is new physics: a drift or a hardware artefact would also replicate. A confirmed candidate needs a new preregistered hardware run on a second backend before it counts as evidence.

## The split (fixed by `split.py`, before anyone looks)

- Data: `data_class == hardware`, not a duplicate copy, with a job id. Dry runs, simulations, histograms without a job id, results of unknown origin and zero-shot results are in neither half.
- Unit: never a shot. One A+B pair (zero_iq, zero_iq_energy_matched, space_memory), one F+N block (c_live, c_live_simultaneous), five consecutive iterations (loop, closed_loop, qpu_vs_rng), otherwise one job.
- Stratum: (family, campaign, unit arm). Inside a stratum units are ordered by SHA-256(seed | unit id); the first half goes to exploration, the second to confirmation; an odd last unit goes by its lowest hash bit.
- The values of the measurements are not read while splitting.
- Result: 204 exploration units (511 jobs) and 201 confirmation units (505 jobs). The unit lists, the job-id lists and two SHA-256 digests per half (unit ids; unit + file + file bytes) are in `split_manifest.json`. Experiments that consist of a single job (spatial_ramsey, spatial_bath_spectroscopy, memory_decay_sweep, each angle-calibration run, several October runs) fall entirely into one half; a candidate based on them can only be confirmed by a new run.
- `python split.py verify`, run on the repos at the commits in `source_repos_at_commit`, must print OK for both halves before the confirmation half is opened.

## Exploration half

Anything may be searched on the exploration half (`python split.py materialize explore`): any variable, any transformation, any subset, any number of looks. Nothing found there is a result.

## Candidates (at most five)

Each candidate is written into `docs/CANDIDATES-pooled_holdout.md` as one exact rule, with:

1. the families and units it applies to (they must have units in the confirmation half);
2. the metric, as a deterministic function of the data, with its code in `scripts/candidate_<n>.py`;
3. the unit of resampling (the split unit) and the null distribution: a permutation of labels or sign flips across units, at least 100,000 resamples, or an exact test;
4. the direction (or "two-sided") and the effect-size threshold below which a significant result still counts as null;
5. what in the exploration half suggested it (effect, p, number of things looked at, roughly).

The file and the scripts are committed and pushed in one commit. Its UTC time must be later than the registration commit of this file and earlier than any access to the confirmation half. No candidate may be added, removed or changed after that commit. More than five candidates: only the first five in the file count.

## Confirmation half

After the candidate commit: `python split.py verify`, then `python split.py materialize confirm --i-have-committed-the-candidates`. Each candidate script runs once on the confirmation half. All outputs are committed, whatever they show.

Decision rule, per candidate, fixed now:

- Holm correction over the number of committed candidates (m ≤ 5), family-wise α = 0.01.
- **Confirmed:** Holm-adjusted p < 0.01, the effect has the committed direction (if one was committed), and its size reaches the committed threshold.
- **Null:** any other outcome: adjusted p ≥ 0.01, the wrong sign, or a significant effect below the threshold. A null candidate is reported as null; it is not re-tested with another metric on the same half.
- If no candidate is committed, the protocol ends with no result.

## What counts as evidence afterwards

A confirmed candidate is a lead, not a finding. It becomes evidence only after a new preregistered hardware run, on a backend not used in the exploration, with a positive control and the same rule, reaches α = 0.01.

## Reporting

The exploration notes (what was looked at, roughly how many things), the candidate file, every confirmation output and the follow-up run are published in the repository whatever they show.
