# Module 3 — Behavioral Analytics and Anomaly Detection

## Scope

Module 3 adds account-history features to the PaySim Isolation Forest experiment. PaySim is simulated, so these results are engineering benchmarks only; they do not demonstrate real-world fraud detection or operational effectiveness.

## Leakage policy

PaySim `step` values represent hourly simulation buckets and do not establish an ordering within a bucket. The feature generator therefore:

1. sorts and processes complete steps chronologically;
2. computes every row's features from state accumulated through earlier steps;
3. updates sender and receiver state only after the complete current step has been transformed.

Raw `nameOrig` and `nameDest` values are used only as state keys. They are not model features. No target or post-transaction balance is used to construct behavioral history.

## Features

The new experiment retains the original numeric features and adds prior-history features for sender and receiver activity:

- prior sender transaction count;
- sender transaction count across the prior three simulation steps;
- prior sender average amount;
- current amount relative to prior sender average;
- prior sender count and share for the current transaction type;
- prior receiver transaction count;
- prior receiver average amount;
- current amount relative to prior receiver average.

For an account without prior history, count and amount-history features are defined as zero. This convention is explicit and tested.

## Reproduce the matched 100k experiment

From the project root:

```bash
python -m src.anomaly_detection.train_isolation_forest_behavioral \
  --csv data/raw/PS_20174392719_1491204439457_log.csv \
  --rows 100000 \
  --out artifacts/anomaly_detection_behavioral
```

The runner reproduces the original Module 3 70% chronological boundary: 72,726 training rows through step 9 and 27,274 test rows beginning at step 10. It evaluates both the original four-feature baseline and the behavioral model on the same test rows, reporting precision and recall at top 10, 50, 100, and 500 alerts.

## Current 1M-row result

The 1M-row matched experiment is stored in `artifacts/anomaly_detection_behavioral_1m`. It uses 699,825 training rows through step 36 and 300,175 test rows from step 37 onward. Both models use the original fixed Isolation Forest configuration; no tuning was performed against the final test period.

| Model | ROC-AUC | Average precision | Top-10 / 50 / 100 / 500 frauds | Top-10 / 50 / 100 / 500 precision |
| --- | ---: | ---: | --- | --- |
| Baseline | 0.6739 | 0.003064 | 0 / 0 / 0 / 2 | 0 / 0 / 0 / 0.004 |
| Behavioral | 0.6362 | 0.012157 | 1 / 2 / 3 / 6 | 0.10 / 0.04 / 0.03 / 0.012 |

The behavioral model improves average precision and captures more fraud at every requested review volume, but its ROC-AUC is lower. The improvement is therefore concentrated in the highest-ranked alerts and should not be summarized as improvement on every metric.

## Account-history coverage

In the 1M-row sample, only 241 of 999,759 origin accounts repeat. Repeated origins account for `0.0482%` of rows. Destination accounts are more reusable: 76,035 of 422,896 repeat, accounting for `65.3139%` of rows. In the chronological test period, only 114 rows (`0.0380%`) have a sender seen during training, versus 154,110 rows (`51.3401%`) with a receiver seen during training. Sender-history features are consequently sparse, while receiver-history features are available for about `58.5%` of test rows.

This dataset limitation explains why receiver-side history is more informative here. It does not justify inventing sender behavior or assuming that the same coverage exists in a real payment system.

The earlier 100k result remains preserved and documented. The next experiment should use a chronological validation period to select targeted receiver-history features before any operational scoring design.
