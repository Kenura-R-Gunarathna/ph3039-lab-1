#import "template2.typ": *
#show: lab_report.with(
  title: "Lab Report: Calibration and Characterization of an NTC Thermistor",
  course: "PH 3039 - Data Acquisition Laboratory",
  student: "H.G. Kenura R.Gunarathna",
  index_no: "s17239",
  partners: "Teshan, Kaveesha",
)
#let todo(t) = highlight(fill: rgb("#fff3a3"))[#t]
#let pair(a, wa, b, wb, cap) = figure(
  grid(columns: (auto, auto), column-gutter: 6pt, align: horizon, image(a, width: wa), image(b, width: wb)),
  caption: cap, kind: image,
)

== Abstract
The objective of this experiment was to calibrate an NTC thermistor as a temperature sensor, check for hysteresis, and find its sensitivity and response time. We used a DS18B20 digital thermometer (±0.5 °C) as the reference, in a stirred water bath from 0 to 98 °C. The NTC was read with a 3.3 kΩ voltage divider and a 10-bit Arduino ADC. We collected one heating and two cooling runs (5321 samples) and fitted a cubic polynomial and the physical NTC β-model. The cubic is $T = 1.869 times 10^(-7) a^3 - 2.495 times 10^(-4) a^2 + 0.2134 a - 17.559$ ($a$ is the ADC count), with a root-mean-square error (RMSE) of 0.54 °C and a *±1.06 °C* 95 % prediction band. The β-model gives β = 3965.3 K and an RMSE of 0.60 °C with only two parameters, so we recommend it. The heating/cooling gap (1.15 °C at most) is smaller than the reference error, so we do not claim real hysteresis. The sensitivity is 0.10–0.25 °C per ADC count, and the time constant is 3.5 s when heating and 7.7 s when cooling. The combined uncertainty is about ±0.5 °C, mostly from the reference.

== 1. Introduction & Theoretical Background
The resistance of an NTC falls steeply and not linearly with temperature, and β is different for every part. So the thermistor must be calibrated against a reference. Here the reference is a *DS18B20* digital thermometer, which works from −55 to +125 °C and is accurate to ±0.5 °C. The ADC uses $V_"cc"$ as its reference, so supply drift cancels. With the Arrhenius law $R(T) = R_0 exp[beta (1 slash T - 1 slash T_0)]$, this gives:
$ r equiv R_"NTC" / R_"f" = (1023 - "ADC") / "ADC", quad ln r = beta / T + c, quad T = 1 / (A ln r + B) - 273.15 quad (A = 1 slash beta) $
The goals are to calibrate the NTC with a polynomial and with this β-model, check for hysteresis, find the sensitivity and the response time, and estimate the uncertainty.

== 2. Experimental Setup & Procedure
=== 2.1 Simulations, Apparatus & Materials
The circuit is a simple voltage divider: the NTC and a 3.3 kΩ fixed resistor in series, with the midpoint read by the ADC (@fig-circ). The 3.3 kΩ resistor keeps the output within the measurable range. (We tried both arrangements of the NTC and the resistor and got approximately similar readings.) An Arduino Uno reads the divider midpoint on pin A2 and the DS18B20 on pin 2 about every 1.5 s. Both sensors sit close together in a stirred water bath, cooled with ice and heated with a hot plate.
#figure(image("figures/circuit.png", width: 38%), caption: [Voltage-divider circuit and reference sensor.]) <fig-circ>

=== 2.2 Experimental Procedure
+ We recorded one heating and two cooling runs between 0 and 98 °C. Other runs had a stuck ADC channel and were not used.
+ We removed empty rows and outliers (beyond 3σ of a first cubic fit; 7 points, all in cooling), then fitted polynomials of degree 1 to 3 and the β-model.
+ For the response time, we moved the NTC repeatedly between room-temperature water and ice water and fitted a delayed first-order model.

== 3. Results & Data Analysis
=== 3.1 Calibration Data Table
After cleaning, we had 1078 heating and 4243 cooling samples from 0 to 98 °C. The cubic fit is the best (@tab-fit). The straight line leaves an S-shaped error of up to about 4 °C. The cubic cuts the RMSE to 0.35 °C for heating and 0.55 °C for cooling, and all its terms are significant ($|t| > 17$). The cooling errors are correlated in time (Durbin–Watson 0.02), so the standard errors are slightly too small.
#figure(
  table(
    columns: 7,
    [Degree], [$R^2$ (H)], [RMSE (H)], [Max (H)], [$R^2$ (C)], [RMSE (C)], [Max (C)],
    [1], [0.99600], [2.326], [3.913], [0.99265], [1.462], [4.010],
    [2], [0.99718], [1.951], [4.146], [0.99882], [0.586], [2.752],
    [3], [*0.99991*], [*0.345*], [*1.459*], [*0.99898*], [*0.546*], [*1.727*],
  ),
  caption: [Fit errors in °C for heating (H, $N = 1078$) and cooling (C, $N = 4243$).], kind: table,
) <tab-fit>

=== 3.2 Model Fitting & Parameter Derivation
We joined the heating and cooling data ($N = 5321$) and fitted one cubic, where $a$ is the ADC count:
$ T = 1.869 times 10^(-7) a^3 - 2.495 times 10^(-4) a^2 + 0.2134 a - 17.559 $
It has $R^2 = 0.999$ and RMSE 0.54 °C. A new reading lies within *±1.06 °C* of the fitted curve with 95 % probability (the mean 95 % prediction half-width). The curve itself is known much better, to about ±0.03 °C (95 % confidence interval).

For the β-model, a straight line of $ln r$ against $1 slash T$ gives $beta = 3965.3$ K, $R^2 = 0.9993$ and an RMSE of *0.598 °C*, using only two parameters.

We compared the heating and cooling cubics over the shared range (ADC 309–849). The biggest gap is *1.15 °C* and the average gap is *0.60 °C*. The likely causes are thermal lag between the NTC and the reference, the fact that the gap is a difference of two cubics, and uneven water temperature. The average gap is smaller than the reference uncertainty, so we do not claim real sensor hysteresis.

The sensitivity $d T slash d"ADC"$ is 0.102–0.195 °C/count for the cubic and 0.101–0.245 °C/count for the β-model (@fig-sens). The sensor reads best in the middle of the range and worse near both ends, where the divider output flattens.
#figure(image("figures/c_models.png", width: 100%), caption: [Left: the fitted cubic and β-model on the data. Middle: sensitivity $d T slash d"ADC"$ of both models. Right: response to a step, as the fraction of the step reached (dotted line: 63 %).]) <fig-sens>
For the response time, we fitted $T(t) = T_f + (T_i - T_f) e^(-(t - t_0) slash tau)$ to 3 clean periods together (@fig-sens, right). The thermistor has $tau = $ *3.5 ± 0.3 s* when heating and *7.7 ± 2.2 s* when cooling (the β-model gives 3.3 s and 8.6 s). Cooling is slower and less certain: one period was much slower, and the ice bath warmed by about 2 °C in period 2.

== 4. Error & Uncertainty Analysis
=== 4.1 Sources of Error
- *Measurement precision:* the DS18B20 is ±0.5 °C (we assume about ±1 °C in practice).
- *ADC resolution:* one count is worth 0.10 to 0.25 °C, coarsest at both ends of the range.
- *Thermal lag:* the NTC and the reference probe have different time constants, so one trails the other when the temperature changes.
- *Self-heating:* $P = I^2 R$ is at most about 1.9 mW with a 5 V supply. We did not measure it.

=== 4.2 Uncertainty Calculations
The regression standard error is 0.54 °C for the cubic and 0.60 °C for the β-model. The combined standard uncertainty adds three independent sources:
$ u_T = sqrt(u_"ref"^2 + (d T slash d"ADC")^2 u_"ADC"^2 + bold(g)^T bold(C) bold(g)) $
Here $u_"ref" = 0.5$ °C, $u_"ADC" = 0.5$ count, $bold(g) = partial T slash partial ("parameters")$ and $bold(C)$ is the parameter covariance matrix. The reference dominates (the ADC term is at most 0.12 °C and the fit term at most 0.04 °C). So the largest $u_T$ is *±0.51 °C* for the cubic and *±0.52 °C* for the β-model, or about ±1.0 °C at 95 %. This is close to the measured RMSE and agrees with the ±1.06 °C prediction band.

== 5. Discussion & Conclusion
Both models calibrate the thermistor to within the ±1 °C uncertainty of the DS18B20, and their RMSE differ by only 0.06 °C. The cubic is slightly better inside the measured range (0–98 °C). The β-model is almost as good with half the parameters, works well outside the range, and gives a real physical constant. The relative sensitivity $alpha = -beta slash T^2$ is about −5.3 %/K at 0 °C and −2.9 %/K at 98 °C. The heating/cooling gap is below the reference uncertainty, so one calibration works for both directions. The final equations are:
$ T = 1.869 times 10^(-7) a^3 - 2.495 times 10^(-4) a^2 + 0.2134 a - 17.559 " °C" quad (plus.minus 1.06 " °C, 95 %") $
$ T = 1 / (2.520 times 10^(-4) ln((1023 - a) slash a) + 3.0842 times 10^(-3)) - 273.15 " °C" quad (beta = 3965.3 " K") $
*Limits.* The reference is only accurate to ±0.5 °C, sensor lag adds error during fast changes, and only three runs were usable, so do not use the cubic outside 0–98 °C. We recommend the β-model as the main calibration.
