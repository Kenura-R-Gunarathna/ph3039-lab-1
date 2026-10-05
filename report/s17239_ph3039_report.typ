#import "template.typ": *
#show: report_template.with(
  title: "Calibrating Temperature Sensors",
  assignment: "PH3039 — Data Acquisition Lab",
)

#let fig(path, cap, label, w: 88%) = [#figure(image("figures/" + path, width: w), caption: cap, placement: none) #label]

= Introduction and Setup
We calibrated an NTC thermistor using a *DS18B20* digital thermometer as the reference. The DS18B20 works from −55 to +125 °C, is accurate to ±0.5 °C, and has a 9–12 bit resolution. Each one has its own 64-bit ID, so many sensors can share a single wire.

The thermistor and a fixed resistor form a voltage divider. A 10-bit ADC (0–1023 counts) reads the divider. We used three good runs: one heating and two cooling. The other runs had a stuck ADC channel. After cleaning, we had 1078 heating and 4241 cooling samples from 0 to 98 °C. We compare polynomial fits (degree 1–3) with the physical NTC β-model.

The DS18B20 uses the 1-Wire interface (one data pin plus ground) and works from 3.0 to 5.5 V. The experiment has two goals: to calibrate the thermistor, and to measure how fast it responds (its time constant).

= Raw Data
Temperature against ADC always goes one way, but it is not a straight line. It is steeper at low counts. The time plots show a slow, smooth change in the water bath temperature, as expected for a thermal transient.

= Heating and Cooling Calibration
#figure(
  table(
    columns: (1fr, auto, auto),
    align: (left, center, center),
    [Item], [Heating], [Cooling],
    [Samples logged], [1079], [4252],
    [Empty (NaN) rows], [1 (ADC 849)], [2],
    [Outliers removed ($> 2.5 sigma$)], [0], [9 (> 1.38 °C)],
    [Samples used in fit], [1078], [4241],
    [Files], [`141803`], [`144604`, `150749`],
  ),
  caption: [Data audit before fitting.], kind: table,
)

We fitted polynomials of degree 1, 2 and 3 to temperature against ADC. For the cooling runs, we removed 2 empty rows and 9 outliers (more than 2.5 standard deviations, or 1.38 °C, from the fit).

#figure(
  table(
    columns: (auto, auto, auto, auto, auto, auto, auto),
    align: center + horizon,
    [Deg.], [$R^2$ (H)], [RMSE (H)], [Max (H)], [$R^2$ (C)], [RMSE (C)], [Max (C)],
    [1], [0.99600], [2.326], [3.913], [0.99266], [1.461], [4.004],
    [2], [0.99718], [1.951], [4.146], [0.99883], [0.584], [2.373],
    [3], [*0.99991*], [*0.345*], [*1.459*], [*0.99898*], [*0.545*], [*1.445*],
  ),
  caption: [Fit errors (°C) for heating (H, $N=1078$) and cooling (C, $N=4241$).],
)

The cubic fit is the best. The straight line leaves an S-shaped error of up to about 4 °C. The cubic cuts the RMSE to 0.35 °C for heating and 0.55 °C for cooling. All cubic terms are significant ($|t| > 18$, $p < 0.001$). The large condition number ($tilde 10^9$) only comes from using raw ADC powers, so it is not a real problem. The cooling errors are strongly correlated in time (Durbin–Watson 0.02), so the quoted standard errors are a little too small.

#figure(
  table(
    columns: (auto, auto, auto, auto, auto),
    align: center + horizon,
    [Coefficient], [Heating], [Cooling], [Global], [Global std. err.],
    [$c_0$ (intercept)], [−18.792], [−8.433], [−17.558], [0.076],
    [$c_1$ (ADC)], [0.2277], [0.1562], [0.2134], [0.001],
    [$c_2$ (ADC²)], [−3×10⁻⁴], [−1×10⁻⁴], [−2.495×10⁻⁴], [1.34×10⁻⁶],
    [$c_3$ (ADC³)], [2.107×10⁻⁷], [1.186×10⁻⁷], [1.869×10⁻⁷], [9.36×10⁻¹⁰],
    [$N$ / AIC], [1078 / 773.8], [4250 / 7028], [5319 / 8544], [—],
  ),
  caption: [Cubic fit coefficients. All terms have $p < 0.001$.],
  kind: table,
)

#figure(
  table(
    columns: (1fr, auto, auto, auto),
    align: (left, center, center, center),
    [Statistic], [Heating], [Cooling], [Global],
    [$F$-statistic], [4.06×10⁶], [1.35×10⁶], [3.22×10⁶],
    [Durbin–Watson], [0.156], [0.022], [0.031],
    [Jarque–Bera], [7.80], [321.1], [466.7],
    [Skew / kurtosis], [0.21 / 2.98], [−0.62 / 2.48], [−0.72 / 2.80],
    [Condition number], [2.6×10⁹], [1.3×10¹⁰], [2.4×10⁹],
  ),
  caption: [Residual checks for the cubic fits.], kind: table,
)
The heating residuals are close to normal (skew 0.2, kurtosis 3). The cooling and global residuals are slightly skewed. This means the fit has a small leftover shape error, so the 95 % band is a rough guide, not an exact limit.

= Heating vs. Cooling Hysteresis
We compared the two cubic fits over the shared range (ADC 309–849). The biggest gap is *1.16 °C* (1.16 % of full scale) and the average gap is *0.61 °C* (@fig-hyst). There are three likely causes:
+ *Thermal lag.* The bead and the reference probe have different time constants $tau = R_"th" C_"th"$, so one sensor trails the other while the temperature changes.
+ *Maths effect.* The gap $Delta T$ is the difference of two cubics, so it is always a smooth wave that crosses zero (here near ADC ≈ 500).
+ *Water bath.* Without good stirring, warm water rises and the two probes see different temperatures.

The average gap is smaller than the reference uncertainty, so we do not claim real sensor hysteresis.

#fig("c11_5.png", [Heating vs. cooling fits and the gap $Delta T$.], <fig-hyst>)

= Global Calibration and 95 % Prediction Band
We joined the heating data and the cleaned cooling data ($N=5319$) and fitted one cubic, where $a$ is the ADC count:
$ T = 1.869 times 10^(-7) a^3 - 2.495 times 10^(-4) a^2 + 0.2134 a - 17.558 $
It has $R^2 = 0.999$ and RMSE 0.54 °C. The mean 95 % prediction half-width is *±1.06 °C* (@fig-pi).

#fig("c14_6.png", [Global cubic fit with its 95 % prediction band.], <fig-pi>)

= Theoretical NTC β-Model
The divider output is $V_"out" = V_"cc" R_"f" slash (R_"NTC" + R_"f")$. The ADC uses $V_"cc"$ as its reference, so the reading does not change if the supply drifts:
$ "ADC" = "ADC"_max dot R_"f" / (R_"NTC" + R_"f") quad => quad r equiv R_"NTC" / R_"f" = (1023 - "ADC") / "ADC". $
Rearranging $"ADC" (R_"NTC" + R_"f") = "ADC"_max R_"f"$ gives $"ADC" dot R_"NTC" = ("ADC"_max - "ADC") R_"f"$. Dividing by $"ADC" dot R_"f"$ gives the ratio $r$ above. Here $"ADC"_max = 1023$ for a 10-bit converter.

In an NTC, heat lifts charge carriers across the band gap $E_g$. This gives the Arrhenius law $R(T) = R_0 exp[beta (1 slash T - 1 slash T_0)]$, with $beta = E_g slash 2k_B$ and $T_0 = 298.15$ K. Dividing by $R_"f"$ and taking the log gives a straight line:
$ ln r = beta / T + c, quad c = ln r_0 - beta / T_0 . $
Let $A = 1 slash beta$ and $B = -c slash beta$. Then solving for temperature gives the formula used in the logger:
$ T = 1 / (A ln((1023 - "ADC") slash "ADC") + B) - 273.15 . $

#figure(
  table(
    columns: (auto, 1fr),
    align: (left, left),
    [Voltage divider], [$r = (1023 - "ADC") slash "ADC"$; cancels $V_"cc"$ noise.],
    [Arrhenius], [$R(T) prop e^(beta slash T)$; carriers excited across $E_g$.],
    [Linear form], [$ln r = beta (1 slash T) + c$; the slope gives $beta = 3965.3$ K.],
    [Runtime], [$T = 1 slash (A ln r + B) - 273.15$; used in the logger.],
  ),
  caption: [Summary of the derivation.], kind: table,
)

= β-Model Validation
We fitted a straight line to $ln r$ against $1 slash T$ (@fig-beta). It gives $beta = 3965.3$ K, $R^2 = 0.9993$ and an RMSE of *0.598 °C*, using only two parameters ($beta$ and $r_0$).

#fig("c17_7.png", [Straight-line Arrhenius fit (left) and β-model accuracy (right).], <fig-beta>)

= Response Time of the Calibrated NTC
// TODO: write the response-time analysis and replace the placeholder box below with the real curve.
#figure(
  rect(width: 100%, height: 6.2cm, stroke: (dash: "dashed", paint: rgb("#94a3b8")), fill: rgb("#f8fafc"), radius: 3pt,
    align(center + horizon, text(fill: rgb("#64748b"), size: 9pt)[Response-time curve \ (calibrated NTC vs. DS18B20 reference)])),
  caption: [Response-time curve of the calibrated NTC (to be added).],
) <fig-resp>
#text(fill: rgb("#64748b"))[_Time constant $tau$, rise time and method: to be added._]

= Sensitivity and Conclusion
The sensitivity $d T slash d"ADC"$ is 0.102–0.195 °C/count for the cubic and 0.101–0.245 °C/count for the β-model (@fig-sens). The sensor reads best in the middle of the range and worse near both ends, where the divider output flattens.

#fig("c20_8.png", [Fitted curves and sensitivity $d T slash d"ADC"$ for both models.], <fig-sens>)

#figure(
  table(
    columns: (auto, auto, auto, 1fr),
    align: (left, center, center, left),
    [Model], [Params], [RMSE], [Notes],
    [Global cubic], [4], [0.54 °C], [Empirical; ±1.06 °C (95 % PI)],
    [NTC β-model], [2], [0.60 °C], [Physical; $beta = 3965$ K, $R^2 = 0.9993$],
  ),
  caption: [Final model comparison.], kind: table,
)

Both models calibrate the thermistor to within the ±1 °C uncertainty of the DS18B20. Their RMSE differ by only 0.06 °C. The cubic is slightly better inside the measured range (0–98 °C). The β-model is almost as good with half the parameters, works well outside the range, and gives a real physical constant.

*Limits of this work.* (1) The reference thermometer is only accurate to ±0.5 °C, and we assumed about ±1 °C in practice, so errors below that cannot be proved. (2) The thermistor and the reference were not at exactly the same temperature during fast changes, which adds lag error. (3) Only three runs were usable, and the calibration covers 0–98 °C only. (4) The cubic should not be used outside this range, because polynomials can turn sharply beyond the data.

#alert(type: "success", title: "Recommendation")[Use the β-model as the main calibration. Use the cubic only when you need the lowest error inside the measured range. The heating/cooling gap (about 0.6 °C on average) is smaller than the reference uncertainty, so one calibration works for both directions.]
