---
type: engineering
title: Data Acquisition Scan — Feeds + Storage under €50/mo
tags: [engineering, data, weather, atc, storage, cost, backfill]
status: draft
updated: 2026-08-09
---

# Data Acquisition Scan — Feeds + Storage ≤ €50/mo

> Cheapest commercial-safe stack to backfill weather + ATC/flight-status into object storage as ML training/testing data, within a **≤€50/mo total data budget**. Consumes [[ingestion-backfill]], [[feature-contract]]. Syncs storage with [[staff-platform-engineer]] cost-model.

> [!important] Headline finding
> The two signals the ML agent flagged as blocked — **the delay label** and **METAR history** — are both obtainable for **~€0**. The €50 ceiling is *not* the binding constraint; **licensing + ops effort** are. Budget is spent almost entirely on storage, which is also ~€1–6/mo. Marks: measured / **estimated** / *assumed*.

## 0. The unblock that costs nothing

- **Delay label is already in the BTS ZIPs we download.** Current `bts_on_time` asset projects only `Cancelled`/`Diverted` (`resources/bts.py` `_BTS_COLUMNS`). BTS On-Time (a.k.a. **ASQP**) also carries `DepDelay`, `ArrDelay`, `ActualElapsedTime`, `WheelsOff/On`, `TaxiOut/In`, and cause splits `CarrierDelay/WeatherDelay/NASDelay/SecurityDelay/LateAircraftDelay`. **Fix = widen the column projection** — no new feed, no cost, public domain. This gives the supervised **delay-minutes label + LateAircraft signal** directly. (measured — BTS field dictionary.)
- **`LateAircraftDelay`** column = a historical late-aircraft label without any live feed.

## 1. Weather feeds

| Source | Coverage | Latency | License / commercial | Cost | Rate limit |
|---|---|---|---|---|---|
| **aviationweather.gov** METAR/TAF | Global METAR + TAF | near-real-time | US-gov **public domain** ✅ | **free** | polite-use; no hard published cap (*assumed*) |
| **NOAA/NWS `api.weather.gov`** | US only | near-real-time | public domain ✅ | **free** | ~fair-use, needs User-Agent (measured) |
| **Iowa IEM ASOS/AWOS/METAR archive** | **Global stations**, decades back (US 1-min 2000–) | historical (batch) | free download; underlying NCEI/ISD/MADIS public; attribution requested — **commercial OK** (measured, verify per-station provenance) | **free** bulk download | bulk endpoint, be gentle |
| **Meteostat** | Global, historical | historical | data **CC BY 4.0** (commercial+attrib); *some* CC BY-NC outside US ⚠️ | data free; API freemium **500 req/mo** free | RapidAPI paid tiers above |
| **OpenWeather** One Call 3.0 | Global | live + 5-day back free; 47yr via paid History | commercial OK | free 1,000 calls/day; PAYG **~$0.0015/call**; bulk history = paid | 1k/day free |
| **Meteomatics** | Global | live + historical | commercial (enterprise) | free trial only; paid likely **> budget** *(assumed)* | trial-limited |

**Pick:** **Iowa IEM** for weather *history* (the ML training unblocker) + **aviationweather.gov** for *live* day-of METAR/TAF. Both free, commercial-safe. Meteostat as an EU/global gap-filler with attribution. Skip OpenWeather bulk-history / Meteomatics (cost).

## 2. ATC / flight-status feeds

| Source | Gives | In budget? | Notes |
|---|---|---|---|
| **BTS ASQP** (already downloaded) | actual times, delay minutes, **cause codes**, late-aircraft | ✅ **free** | US, ~3mo lag; the training label (see §0) |
| **FAA ASPM / OPSNET** | actual gate/taxi times, airport throughput, delay attribution | ✅ free (account-gated) | US; batch, not a clean REST API; enriches labels |
| **FAA NAS Status** (`nasstatus.faa.gov`) | **GDP / ground-stop / ground-delay** advisories | ✅ **free**, easy | US; the strongest *day-of* signal, low ops |
| **FAA SWIM** (SCDS) | real-time TFMS: GDP, ground-stops, actual times | ✅ data free, ⚠️ **heavy ops** (JMS/Solace consumer) | US; free but infra-costly — defer |
| **Eurocontrol NM B2B** | EU flight plans, regulations, actual times, live | ⚠️ access restricted to aviation stakeholders | Startups rarely granted; use **ADRR** (free, 2yr delay) instead ([[ingestion-backfill]]) |
| **FlightAware AeroAPI** | live actual times, status, Foresight | ✅ **Personal ~$5/mo free**, $0.002/query, no min | commercial OK; low-volume spot/live enrichment fits budget |
| **aviationstack** | global live + historical status | ⚠️ **$49.99/mo** = whole budget | commercial OK; too pricey for backfill volume |
| **AviationEdge** | schedules/status/historical | subscription *(price assumed ~$ tens/mo)* | verify before use |
| **ADS-B Exchange** | raw ADS-B live + historical | RapidAPI **$10/mo/10k**; commercial = enterprise annual commit | 10yr backfill subscribers-only; RapidAPI tier commercial-ambiguous ⚠️ |
| **OpenSky** | global ADS-B historical | free but **non-commercial** ❌ | dev/backtest only (unchanged) |

**GDP / late-aircraft / actual-times within budget:** GDP → **FAA NAS Status** (free); actual-times + late-aircraft label → **BTS ASQP** (free, batch) + **FlightAware AeroAPI Personal** (~free, live spot). SWIM gives richer real-time GDP but the ops cost isn't worth it pre-revenue.

## 3. Storage — correct the "Glacier for training data" assumption

**Glacier/Deep-Archive is the wrong tier for training data.** You read training sets repeatedly (every epoch / every experiment). Deep Archive: **$0.00099/GB-mo** storage *but* retrieval **3–48 h latency**, **$0.0025–0.03/GB retrieval fee**, **180-day minimum**, plus per-request + egress. Iterative reads turn that into latency pain + surprise retrieval bills. Glacier is only right for a **cold raw archive you almost never read**.

### Recommended warm + cold split

| Tier | What lives here | Store | Rate | Why |
|---|---|---|---|---|
| **Warm** | derived Parquet train/test sets + active weather (read every epoch) | **Cloudflare R2 Standard** | **$0.015/GB-mo, $0 egress**, 10GB free | $0 egress is decisive for iterative reads; R2-IA $0.01/GB if colder |
| **Cold** | original raw dumps (BTS ZIPs, raw METAR pulls) for reproducibility | **Glacier Deep Archive** or **R2 Infrequent Access** | Glacier $0.00099/GB-mo | rarely re-read; keep only to re-derive |

### Cost math (mark: **estimated**)

- BTS: ~**2–4 GB** derived Parquet (10yr nationwide, [[ingestion-backfill]] §1.2) + raw ZIPs ~**4.8 GB**.
- Weather (IEM): global METAR 10yr Parquet ≈ **10–30 GB** (est. ~3,000 stations × ~8,760 obs/yr × 10yr × ~200 B, compressed); US-only ≈ 3–8 GB.
- **Warm working set ≈ 20–50 GB** → R2 Standard: 50 GB × $0.015 = **$0.75/mo**, egress **$0** → **≈ €0.7/mo**.
- **Cold raw ≈ 5–10 GB** → Glacier Deep Archive: 10 GB × $0.00099 = **$0.01/mo** (retrieval only on rare re-derive).
- Ops (Class A/B): well within R2 free tier for our write cadence.
- **Total storage ≈ €1/mo; total data stack (feeds + storage) ≈ €1–6/mo** ✅ — vast headroom under €50.

### Sync with [[staff-platform-engineer]]
- Current store is **self-hosted SeaweedFS** (`docker-compose.yml`). If we stay self-hosted, marginal storage cost ≈ **€0** (rides the existing VPS) but **durability/backup** is the risk → replicate the **cold raw** copy to Glacier/R2-IA off-box. If going cloud-native, **R2** (zero egress) beats S3-Standard for training reads. **Host decision is [[staff-platform-engineer]]'s** — this note gives them the storage-tier + volume numbers for the cost-model.

## Open questions
- [ ] Confirm IEM/Meteostat per-station commercial provenance (some NC segments). `#task/eng 🔼`
- [ ] Widen BTS column projection to emit delay label + cause codes (cheap, unblocks ML). `#task/eng 🔺 ⛓ [[feature-contract]]`
- [ ] Self-hosted SeaweedFS vs cloud R2 for warm tier — decide with [[staff-platform-engineer]]. `#task/eng`

## Sources
- [Iowa IEM ASOS/METAR download](https://mesonet.agron.iastate.edu/request/download.phtml) · [IEM metar dataset](https://mesonet.agron.iastate.edu/info/datasets/metar.html) — accessed 2026-08-09
- [aviationweather.gov](https://aviationweather.gov/) · [NWS api.weather.gov](https://www.weather.gov/documentation/services-web-api) — accessed 2026-08-09
- [Meteostat license](https://dev.meteostat.net/terms.html) · [Meteostat API](https://dev.meteostat.net/api) — accessed 2026-08-09
- [OpenWeather pricing](https://openweathermap.org/price) · [One Call 3.0](https://openweathermap.org/api/one-call-3) — accessed 2026-08-09
- [FlightAware AeroAPI pricing](https://www.flightaware.com/commercial/aeroapi/v3/pricing.rvt) — accessed 2026-08-09
- [aviationstack pricing](https://aviationstack.com/pricing) · [ADS-B Exchange RapidAPI](https://rapidapi.com/adsbx/api/adsbexchange-com1/pricing) — accessed 2026-08-09
- [Cloudflare R2 pricing](https://developers.cloudflare.com/r2/pricing/) — accessed 2026-08-09
- [S3 Glacier Deep Archive pricing guide](https://www.usage.ai/blogs/aws/storage-cost/glacier-deep-archive-pricing/) — accessed 2026-08-09
- FAA NAS Status `https://nasstatus.faa.gov/` ; BTS On-Time/ASQP field dictionary `https://www.transtats.bts.gov/` — accessed 2026-08-09
- Repo: `pipeline/pipeline/resources/bts.py`, `docker-compose.yml` — accessed 2026-08-09
