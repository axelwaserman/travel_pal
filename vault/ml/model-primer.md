---
type: ml
title: Model Primer — Plain-Language Guide to What We're Building
tags: [ml, primer, teaching, lightgbm, conformal]
status: draft
updated: 2026-08-09
---

# Model Primer

> A ~5-minute, jargon-light explanation of the models behind TravelPal's four predictions, grounded in what we actually chose ([[model-selection]]: LightGBM + conformal). See also [[problem-framing]], [[features]].

## Start from what you know

- **Regression** = fit a function mapping inputs → a number. Plain *linear* regression assumes a straight-line, additive relationship. Our data breaks that: delays are **right-skewed** (most flights ~on-time, a long tail of huge delays), **zero-inflated** (a spike at "0 min late"), and driven by **nonlinear interactions** (bad weather × evening hub × regional carrier compounds). A straight line fits none of this.
- **Gradient-boosted trees (GBTs — we use LightGBM)** *generalize* regression: instead of one line, they sum hundreds of small decision trees, each correcting the last. Trees split on thresholds, so they capture skew, kinks, and interactions automatically — and handle categories (carrier, airport) and missing values natively. That's why they, not linear models, are our workhorse.
- **Clustering** (k-means etc.) is *unsupervised* — it groups similar flights with **no labels**. It cannot predict lateness because it never sees the answer. Side-use only: segmenting airports/routes or engineering features.
- **Neural nets** win on images/text/huge sequence data. On **tabular** data at our scale they don't beat GBTs, and cost more (GPUs, more data, more ops). So GBTs first; a Temporal Fusion Transformer (a sequence-aware net) stays a *later* option if delay-propagation signal proves worth it.

## The four targets

**1. Likelihood of lateness — P(delay ≥ 15/60/180 min).** *Binary classification, one per threshold* ("classification" = predict a category; here yes/no late-beyond-X). LightGBM outputs a probability; we read the three thresholds off the predicted delay **distribution** so they stay consistent (60-min risk ≤ 15-min risk).

**2. Most likely cause(s) — BTS cause codes** (carrier / weather / NAS-air-traffic / late-aircraft / security). *Multilabel classification* — "multilabel" because more than one cause can apply at once. But the user-facing "why" comes from **SHAP** (one line: SHAP tells you how much each input pushed *this* prediction up or down). SHAP turns the black box into "delayed mostly because of forecast weather at origin + a late inbound aircraft" — that explanation **is** our transparency wedge.

**3. Delay duration (minutes).** *Quantile regression* (one line: predicts a range — e.g. the 10th/50th/90th percentile — instead of a single average). Because the tail is skewed, an average is misleading; quantiles give an honest band (`p10`–`p90`). LightGBM trains directly on a quantile objective.

**4. Likelihood of cancellation.** *Binary classification*, but cancellations are **rare** — "class imbalance" (one line: one outcome is far scarcer, so a naive model just predicts "never" and looks accurate). We correct with class weighting and judge on calibration, not raw accuracy. Modeled separately from delay because a cancelled flight has no delay minutes.

## Two glue concepts

- **Calibration** (one line: when we say 70%, it's late 70% of the time). We wrap every probability in **conformal calibration** so the stated number is trustworthy — for us, calibration beats chasing a bigger accuracy headline.

## How they combine — and the regional split

All four run behind one API call and merge into a single response: `p_delay_{15,60,180}`, `expected_delay_min` + `p10/p90` band, `cancel_prob`, and `reason_codes[]` (the SHAP causes). One flight in → one calibrated, explained answer out.

We train **two regional models — `model_us` and `model_eu`** — using this *identical* recipe (same tasks, LightGBM, conformal). Region is just a partition across our shared pipeline, storage, and serving. `model_us` rides a deep BTS backfill; `model_eu` starts thin on AeroDataBox, cold-starting on base-rates + deliberately wide bands and sharpening monthly as its history grows.

## FAQ — GBTs vs XGBoost vs LightGBM

**1. How are they related — algorithm vs implementation?** Yes: **"gradient-boosted trees" (GBT) is the technique** — build many small decision trees in sequence, each trained to correct the previous ones' errors. **XGBoost and LightGBM are libraries that implement and train it** (like two vendors' engines for the same idea). Neither is pure textbook GBT; each adds its own tweaks — XGBoost pioneered regularization + a clever second-order optimization; LightGBM added faster growth and binning strategies. Same core idea, different engineering.

**2. Are they interchangeable? What differs?** Broadly yes — comparable accuracy on most tabular problems. Real differences: **tree growth** — LightGBM grows *leaf-wise* (splits the single most useful leaf next → deeper, faster-converging trees), XGBoost historically *level-wise* (whole layer at a time). **Histogram binning** (one line: bucket continuous values into ~255 bins so splits are cheap) — LightGBM leaned into this first for speed/memory. **Categorical handling** — LightGBM takes categories natively; XGBoost long needed manual encoding (now has some support). Net: LightGBM is usually faster and lighter on memory; XGBoost is battle-tested and sometimes more robust on small/noisy data.

**3. Why LightGBM here?** Concrete fits: (a) **native categorical support** — carrier and airport are high-cardinality categories, and LightGBM ingests them directly (no one-hot blow-up); (b) **speed/memory** on our large row counts (deep BTS backfill); (c) **quantile objective** built in, which we need for the `p10`–`p90` delay band. Honestly it's a close call — **XGBoost would also work**; LightGBM just wins on ergonomics for *this* categorical-heavy, wide-data problem. Not a religious choice.

## FAQ — point/mean prediction & LightGBM vs XGBoost revisited

**1. Term collision (important).** Two unrelated senses of "categorical" are getting crossed. **Input features** carrier/airport are categorical *inputs* — LightGBM's "native categorical" perk is only about *encoding those inputs*. **The output** — a delay in minutes — is a **number**, so predicting it is **regression** either way. Both libraries do that regression *identically in kind*. Point-vs-range output is **orthogonal** to input encoding: LightGBM's input perk neither helps nor hurts a mean prediction. So "not categorical" refers to the output, and it doesn't change the library comparison.

**2. The headline number.** Three choices for one number: **mean** (average), **median = p50** (middle), **mode** ("most likely single value"). Delay is right-skewed (long tail of big delays), so the **mean overstates** — a few 4-hour delays drag it up. The honest headline is **p50 (median)**, and it drops straight out of the quantile model we already planned: p50 is just another quantile alongside p10/p90. So one recipe yields "most likely ~X min (p50)" **plus** the p10–p90 band **plus** the P(delay≥15/60/180) threshold odds — coherently. Both libraries support point (squared-error) *and* quantile objectives.

**3. Compute premise.** LightGBM's edge is **not** memory-only — on CPU it's usually **faster to train too** (leaf-wise growth + histogram binning). XGBoost's `hist`/GPU modes narrow that gap a lot. **Inference latency is sub-millisecond for both** and a non-factor at our scale. So "both fast → prefer XGBoost" doesn't really hold; if anything CPU training tips slightly to LightGBM.

**4. Is XGBoost "more versatile"?** Practically no. Both offer custom objectives, quantile, monotonic constraints, SHAP, multi-output, and a scikit-learn API. For our plausible needs it's **parity** — "versatility" isn't a real differentiator. Pick on ergonomics; both are safe, and switching later is cheap.
