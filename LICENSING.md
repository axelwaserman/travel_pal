# Third-Party Licensing Notes

## Highcharts

This project uses [Highcharts](https://www.highcharts.com/) under the **free
non-commercial license**. Highcharts is free for personal use, school websites,
and non-profit organisations. Commercial use requires a paid license — see
https://shop.highcharts.com/.

If TravelPal is later commercialised (paid hosting, paid API access, ad-funded
deployment, B2B SaaS), Highcharts MUST be replaced with an Apache/MIT
alternative (ECharts, Recharts, uPlot) before launch.

## OurAirports (`pipeline/transforms/seeds/dim_airport.csv`)

Public-domain airport reference data from <https://ourairports.com/data/>.
Released under Creative Commons Public Domain Dedication.

## OpenFlights Airlines (`pipeline/transforms/seeds/dim_carrier.csv`)

Airline reference data from <https://openflights.org/data.html>. Released under
the OpenFlights Database License (ODbL). Last upstream update: 2017 — adequate
for established US carriers, may miss recent regional/cargo entrants.

## BTS On-Time Performance

Source: U.S. Department of Transportation Bureau of Transportation Statistics,
<https://transtats.bts.gov/>. Public-domain US government data.
