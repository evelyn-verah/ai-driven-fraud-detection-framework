# Module 1 — Data ingestion and feature engineering

## Goal
Build a reproducible ingestion layer with separate dataset adapters. No model performance claims are made by this module.

## Dataset placement
Download PaySim yourself and place its **original unmodified CSV** at `data/raw/PS_20174392719_1491204439457_log.csv`. The actual PaySim CSV is **not included** in this project.

## Inspect first 100,000 rows
Run from project root:

```bash
python -m src.ingestion.cli --dataset paysim --csv data/raw/PS_20174392719_1491204439457_log.csv --rows 100000
```

## Generate a prepared sample

```bash
python -m src.ingestion.cli --dataset paysim --csv data/raw/PS_20174392719_1491204439457_log.csv --rows 100000 --out data/processed/paysim_sample_100k.csv
```

This generates a bounded sample, **not a production-ready training split**. The earliest rows may have an unrepresentative fraud rate. Later training must use a chronological holdout, ensure both classes appear in each split, avoid fitting preprocessing on test data, and avoid features unavailable at transaction decision time.

## Leakage policy
PaySim `isFraud` is the target; `isFlaggedFraud` is a rule baseline, not a predictor. `newbalanceOrig` and `newbalanceDest` are omitted because they may reflect post-transaction state. Raw sender and receiver IDs are excluded pending careful historical feature generation. `step`, `type`, `amount`, `oldbalanceOrg`, `oldbalanceDest` are initial candidate predictors; verify availability in the intended scoring workflow.

## Data boundaries
Do not merge PaySim customer IDs with BankSim or IEEE-CIS identities. BankSim adapter currently supports **schema inspection only**. IEEE-CIS ingestion remains planned. Security telemetry is a separate future input source.

## Run tests

```bash
python -m pytest -q
```
