#import "template.typ": *
#show: report_template.with(
  title: "Calibrating Temperature Sensors",
  assignment: "PH3039 — Data Acquisition Lab",
)

#let fig(path, cap, label, w: 55%) = [#figure(image("figures/" + path, width: w), caption: cap, placement: none) #label]

= Introduction and Setup
In this experiment, we calibrated an NTC thermistor using a *DS18B20* digital thermometer as the reference. The DS18B20 works from −55 to +125 °C, is accurate to ±0.5 °C, and has a 9–12 bit resolution.

The circuit is a simple voltage divider with the NTC connected on one side to GND. (We tried both configurations and got approximately similar readings within a 99% confidence interval.) A 10-bit ADC (0–1023 counts) reads the divider. For the calibration we collected 3 runs: one heating and two cooling. After cleaning, we had 1078 heating and 4243 cooling samples from 0 to 98 °C. We fitted the readings in two ways: polynomials of degree 1 to 3, and the physical NTC β-model. We also measured how fast the thermistor responds (its time constant).

= Raw Data
Temperature falls steadily as ADC counts rise, but not linearly: the curve is steeper at low counts. The time plots show a slow, smooth change in bath temperature.

= Heating and Cooling Calibration
#figure(
  table(
    columns: (1fr, auto, auto),
    align: (left, center, center),
    [Item], [Heating], [Cooling],
    [Samples logged], [1079], [4252],
    [Empty (NaN) rows], [1 (ADC 849)], [2],
    [Outliers removed ($> 3 sigma$)], [0], [7 (> 1.66 °C)],
    [Samples used in fit], [1078], [4243],
  ),
  caption: [Data audit before fitting.], kind: table,
)

We fitted polynomials of degree 1 to 3 to temperature against ADC. Empty rows and outliers (beyond 3 standard deviations of the first cubic fit, or 1.66 °C for the cooling runs) were removed first. We used the common 3σ cut; the earlier 2.5σ cut removed 2 more points and changed the RMSE by less than 0.01 °C.

#figure(
  table(
    columns: (auto, auto, auto, auto, auto, auto, auto),
    align: center + horizon,
    [Deg.], [$R^2$ (H)], [RMSE (H)], [Max (H)], [$R^2$ (C)], [RMSE (C)], [Max (C)],
    [1], [0.99600], [2.326], [3.913], [0.99265], [1.462], [4.010],
    [2], [0.99718], [1.951], [4.146], [0.99882], [0.586], [2.752],
    [3], [*0.99991*], [*0.345*], [*1.459*], [*0.99898*], [*0.546*], [*1.727*],
  ),
  caption: [Fit errors (°C) for heating (H, $N=1078$) and cooling (C, $N=4243$).],
)

The cubic fit is the best. The straight line leaves an S-shaped error of up to about 4 °C. The cubic cuts the RMSE to 0.35 °C for heating and 0.55 °C for cooling. All cubic terms are significant ($|t| > 17$, $p < 0.001$). The large condition number ($tilde 10^9$) comes from using raw ADC powers and is harmless. The cooling errors are correlated in time (Durbin–Watson 0.02), so the standard errors are slightly too small.

#figure(
  table(
    columns: (auto, auto, auto, auto, auto),
    align: center + horizon,
    [Coefficient], [Heating], [Cooling], [Global], [Global std. err.],
    [$c_0$ (intercept)], [−18.792], [−7.364], [−17.559], [0.076],
    [$c_1$ (ADC)], [0.2277], [0.1495], [0.2134], [0.001],
    [$c_2$ (ADC²)], [−2.848×10⁻⁴], [−1.240×10⁻⁴], [−2.495×10⁻⁴], [1.34×10⁻⁶],
    [$c_3$ (ADC³)], [2.107×10⁻⁷], [1.107×10⁻⁷], [1.869×10⁻⁷], [9.36×10⁻¹⁰],
    [$N$ / AIC], [1078 / 773.8], [4243 / 6914], [5321 / 8557], [—],
  ),
  caption: [Cubic fit coefficients. All terms have $p < 0.001$.],
  kind: table,
)

#figure(
  table(
    columns: (1fr, auto, auto, auto),
    align: (left, center, center, center),
    [Statistic], [Heating], [Cooling], [Global],
    [$F$-statistic], [4.06×10⁶], [1.38×10⁶], [3.21×10⁶],
    [Durbin–Watson], [0.156], [0.022], [0.031],
    [Jarque–Bera], [7.80], [325.3], [468.2],
    [Skew / kurtosis], [0.21 / 2.98], [−0.53 / 2.16], [−0.72 / 2.80],
    [Condition number], [2.6×10⁹], [1.35×10¹⁰], [2.4×10⁹],
  ),
  caption: [Residual checks for the cubic fits.], kind: table,
)
The heating residuals are close to normal (skew 0.2, kurtosis 3). The cooling and global residuals are slightly skewed, which means a small shape error remains, so the 95 % band is a rough guide.

= Heating vs. Cooling Hysteresis
We compared the two cubic fits over the shared range (ADC 309–849). The biggest gap is *1.15 °C* (1.15 % of full scale) and the average gap is *0.60 °C* (@fig-hyst). There are three likely causes:
+ *Thermal lag.* The NTC and the reference probe have different time constants $tau = R_"th" C_"th"$, so one sensor trails the other while the temperature changes.
+ *Maths effect.* $Delta T$ is the difference of two cubics, so it is a smooth wave crossing zero (near ADC ≈ 500).
+ *Water bath.* Without good stirring, the two probes see different temperatures.

The average gap is smaller than the reference uncertainty, so we do not claim real sensor hysteresis.

#fig("c11_5.png", [Heating vs. cooling fits and the gap $Delta T$.], <fig-hyst>)

= Global Calibration and 95 % Prediction Band
We joined the heating data and the cleaned cooling data ($N=5321$) and fitted one cubic, where $a$ is the ADC count:
$ T = 1.869 times 10^(-7) a^3 - 2.495 times 10^(-4) a^2 + 0.2134 a - 17.559 $
It has $R^2 = 0.999$ and RMSE 0.54 °C. The mean 95 % prediction half-width is *±1.06 °C* (@fig-pi).

#fig("c14_6.png", [Global cubic fit with its 95 % prediction band.], <fig-pi>)

= Theoretical NTC β-Model
The divider output is $V_"out" = V_"cc" R_"f" slash (R_"NTC" + R_"f")$. The ADC uses $V_"cc"$ as its reference, so the reading does not change if the supply drifts:
$ "ADC" = "ADC"_max dot R_"f" / (R_"NTC" + R_"f") quad => quad r equiv R_"NTC" / R_"f" = (1023 - "ADC") / "ADC". $

In an NTC, heat lifts charge carriers across the band gap $E_g$. This gives the Arrhenius law $R(T) = R_0 exp[beta (1 slash T - 1 slash T_0)]$, with $beta = E_g slash 2k_B$ and $T_0 = 298.15$ K. Dividing by $R_"f"$ and taking the log gives a straight line:
$ ln r = beta / T + c, quad c = ln r_0 - beta / T_0 . $
Let $A = 1 slash beta$ and $B = -c slash beta$. Then solving for temperature gives the formula used in the logger:
$ T = 1 / (A ln((1023 - "ADC") slash "ADC") + B) - 273.15 . $

= β-Model Validation
We fitted a straight line to $ln r$ against $1 slash T$ (@fig-beta). It gives $beta = 3965.3$ K, $R^2 = 0.9993$ and an RMSE of *0.598 °C*, using only two parameters ($beta$ and $r_0$).

#fig("c17_7.png", [Straight-line Arrhenius fit (left) and β-model accuracy (right).], <fig-beta>)

= Response Time of the Calibrated NTC
We dipped the probe repeatedly into ice water (0 °C) and room-temperature water, giving a square-wave input. After removing one spike (at 496 s) and the first cycle, 3 full periods remained. We converted ADC to °C with both the cubic and the β-model, then fitted Newton's law with a start delay to the 3 periods together:
$ T(t) = T_f + (T_i - T_f) e^(-(t - t_0) slash tau) . $
The 3 periods share $tau$, $T_i$ and $T_f$; each has its own delay $t_0$. The error comes from leaving one period out at a time (@fig-resp).

#fig("c_response.png", [Pooled fit (cubic calibration) of the 3 heating and 3 cooling steps.], <fig-resp>, w: 100%)

#figure(
  table(
    columns: (auto, auto, auto, auto, auto),
    align: center + horizon,
    [Step], [Calibration], [$tau$ (s)], [10–90 % (s)], [RMSE (°C)],
    [Heating], [Cubic], [3.5 ± 0.3], [7.8], [0.47],
    [Heating], [β-model], [3.3 ± 0.3], [7.3], [0.50],
    [Cooling], [Cubic], [7.7 ± 2.2], [16.8], [0.92],
    [Cooling], [β-model], [8.6 ± 2.2], [18.9], [1.02],
  ),
  caption: [Response time from the pooled fits (± is the leave-one-out error).], kind: table,
)

The thermistor reaches 63 % of a step in about *3.4 s* when heating and about *8 s* when cooling, so it needs roughly 17 s and 40 s to settle (5 $tau$). The two calibrations agree within 1 s, less than the error, so the choice does not matter. Cooling is slower and less certain: one period was much slower, and the ice bath warmed by about 2 °C during period 2, which a single exponential cannot follow (RMSE about 1 °C).

= Sensitivity and Error Theory
The sensitivity $d T slash d"ADC"$ is 0.102–0.195 °C/count for the cubic and 0.101–0.245 °C/count for the β-model (@fig-sens). The sensor reads best mid-range and worse near both ends, where the divider output flattens.

#fig("c20_8.png", [Fitted curves and sensitivity $d T slash d"ADC"$ for both models.], <fig-sens>)

RMSE only measures scatter around the fit. To predict the error from its sources, we propagate three independent ones, $u_T^2 = sum_i (partial T slash partial x_i)^2 u_(x_i)^2$:
$ u_T = sqrt(u_"ref"^2 + (d T slash d"ADC")^2 u_"ADC"^2 + bold(g)^T bold(C) bold(g)) . $
$u_"ref" = 0.5$ °C is the DS18B20 accuracy. The ADC rounds to the nearest count ($u_"ADC" = 0.5$), giving $u_"res" = |d T slash d"ADC"| dot 0.5$, so a flat region reads coarsely. The fit term uses the parameter covariance $bold(C)$ and $bold(g) = partial T slash partial "params"$ (with cross terms, as the coefficients are correlated).

#figure(
  table(
    columns: (1fr, auto, auto),
    align: (left, center, center),
    [Quantity (°C)], [Cubic], [β-model],
    [Resolution, $|d T slash d"ADC"|_max$ (°C/count)], [0.195], [0.245],
    [$u_"res"$ (max)], [0.097], [0.122],
    [$u_"fit"$ (mean / max)], [0.016 / 0.037], [0.012 / 0.026],
    [$u_"ref"$], [0.5], [0.5],
    [*$u_T$ (mean / max)*], [*0.505 / 0.510*], [*0.505 / 0.515*],
    [Measured RMSE], [0.54], [0.60],
    [Largest residual], [1.56], [1.46],
  ),
  caption: [Error theory compared with the measured errors.], kind: table,
)

The reference error dominates; the fit and resolution terms add less than 0.1 °C each. The theory gives $u_T approx 0.51$ °C, close to the measured RMSE (0.54 and 0.60 °C). The small extra part ($tilde 0.2$–$0.3$ °C) is what the theory leaves out: thermal lag, hysteresis and model shape error. We quote the *largest* $u_T$ over the range as the standard error: *±0.51 °C (cubic)* and *±0.52 °C (β-model)*, or about ±1.0 °C at 95 % (two standard deviations), which agrees with the ±1.06 °C prediction band.

= Conclusion

Both models calibrate the thermistor to within the ±1 °C uncertainty of the DS18B20. The global cubic (4 parameters) has RMSE 0.54 °C and ±1.06 °C (95 % PI); the β-model (2 parameters, $beta = 3965$ K, $R^2 = 0.9993$) has RMSE 0.60 °C. Error theory gives the same ±0.5 °C for both because the reference dominates. The cubic is slightly better inside 0–98 °C. The β-model is almost as good with half the parameters, works well outside the range, and gives a real physical constant.

*Limits.* The DS18B20 is only accurate to ±0.5 °C, so smaller errors cannot be proved. Lag between the two sensors adds error during rapid changes. Only three runs were usable (0–98 °C), so do not use the cubic outside this range.

#alert(type: "success", title: "Recommendation")[Use the β-model as the main calibration, and the cubic only when you need the lowest error inside 0–98 °C. The heating/cooling gap (about 0.6 °C) is below the reference uncertainty, so one calibration works for both directions.]
