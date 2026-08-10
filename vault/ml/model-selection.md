---
type: ml
title: Model Family Selection — Recommendation
tags: [ml, model-selection, lightgbm, quantile, conformal]
status: draft
updated: 2026-08-08
---

# Model Family Selection

> EVALUATE → RECOMMEND. Consumes [[problem-framing]] (three tasks), [[features]] (tabular + temporal + weather), [[serving-deployment]] (latency budget). Feeds [[training-orchestration]], [[evaluation]].

## Recommendation (one line)

**LightGBM** for all three heads — a **binary classifier (cancellation, T1)**, **multi-quantile regressor (delay magnitude + exceedance, T2/T3)** — **wrapped in split-conformal calibration (CQR for intervals, isotonic/Venn-Abers for probabilities)**. Ship this as v1; keep a sequence model as a *later* experiment, gated on evidence.

## Candidate evaluation

| Family | Fit for our factors | Verdict |
|---|---|---|
| **GBM — LightGBM** ✅ | Native categorical (carrier/airport, high cardinality) with no one-hot blow-up; `quantile` + `binary` objectives; CPU inference ~ms fits the in-proc `<30 ms` budget ([[serving-service]]); tiny artifact; monotone constraints available | **Recommended baseline** |
| GBM — CatBoost | Best-in-class categorical + ordered boosting; strong when categoricals dominate | **Alt** if carrier/airport cardinality hurts LightGBM; heavier artifact/deps |
| GBM — XGBoost | Comparable accuracy; categorical + quantile support now exist but less ergonomic; historically quantile-crossing pain | Fallback, no advantage here |
| **Quantile regression (GBM objective)** ✅ | Directly yields `p10/p90` band + full CDF for `P(delay≥t)` — exactly [[feature-contract]] §C | **Recommended** — it *is* the T2/T3 estimator (LightGBM `objective=quantile`, one model per quantile or a multi-target wrapper) |
| TFT / seq models (PyTorch) | Would capture delay-*propagation* chains (late-aircraft) and intraday sequence | **Deferred.** Tabular data + our feature set: GBMs match/beat deep nets on tabular (Grinsztajn 2022; Shwartz-Ziv & Armon 2022). Ops cost (GPU, PyTorch footprint) violates "keep footprint small" ([[AGENTS]] rule 3). Revisit only if a **paid live feed** unlocks true sequence signal and a backtest shows lift. |
| **Conformal wrapper** ✅ | Distribution-free coverage guarantee on the band; upgrades honesty of the shown probability | **Recommended** — CQR (Romano 2019) over the quantile heads; isotonic or Venn-Abers on the classifier |

## Why calibration layer is mandatory, not optional

Raw GBM class scores and quantile crossings are **not** guaranteed calibrated. [[research-summary]]/[[differentiation-thesis]] make calibration the product wedge and [[personas]] P4 (insurers) buy on it. Plan:

- **T2/T3 intervals:** Conformalized Quantile Regression (CQR) → finite-sample marginal coverage on a held-out calibration split; recompute per training snapshot.
- **T1 & threshold probs:** isotonic regression or **Venn-Abers** (distribution-free, gives probability intervals) fit on the same calibration window; report reliability/Brier ([[evaluation]]).
- Calibration reference sets differ for booking vs day-of regimes ([[problem-framing]]).

## Factors → features the family must exploit

Route, carrier, aircraft/tail, scheduled hour, day-of-week, season/holiday, origin+dest congestion, **weather at origin/dest (METAR/TAF)**, GDP/ground-stop, and **late-aircraft propagation** (paid-feed-gated). GBMs handle these mixed categorical+numeric+missing signals natively with graceful degradation when §B fresh features are stale ([[features]]).

## Proposed additions to the locked stack (justify + minimal)

| Lib | Why | Footprint |
|---|---|---|
| **LightGBM** | baseline estimator; CPU-only; native categorical + quantile | small wheel, no GPU |
| **MAPIE** *(or hand-rolled split-conformal)* | CQR/conformal calibration | pure-Python, thin |
| scikit-learn | isotonic/Venn-Abers, metrics, splitting | already ubiquitous |

PyTorch/TFT/ONNX **not** proposed for v1. All are Pre-Code-Gate additions ([[AGENTS]] rule 3, `CLAUDE.md`).

## External benchmarks (cited; NOT our targets)

- Grinsztajn, Oyallon, Varoquaux 2022, *"Why do tree-based models still outperform deep learning on typical tabular data?"* — NeurIPS D&B. (marks: external/measured-elsewhere)
- Shwartz-Ziv & Armon 2022, *"Tabular Data: Deep Learning is Not All You Need"*, Information Fusion.
- Romano, Patterson, Candès 2019, *"Conformalized Quantile Regression"*, NeurIPS.
- Flight-delay literature commonly reports GBMs as strong tabular baselines; any accuracy figures there are **external/estimated** and are **not** adopted as TravelPal targets ([[evaluation]] sets targets post-backtest).

## Handoff

- → [[training-orchestration]]: three LightGBM training assets + a conformal-calibration asset per snapshot.
- → [[serving-deployment]]: native booster load, in-proc predict, conformal maps shipped with the artifact.
- ↔ [[staff-product-engineer]]: confirm categorical encoding contract (native LightGBM categorical indices vs pre-encoded) in the `feature_vector`.

## Sources

- [[problem-framing]], [[features]], [[serving-service]] latency budget — repo vault, accessed 2026-08-08
- External papers above — public literature, accessed 2026-08-08
