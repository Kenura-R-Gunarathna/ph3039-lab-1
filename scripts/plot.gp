# gnuplot -c plot.gp <csv> <png>
csv = ARG1
out = ARG2

set terminal png size 1800,500 font "Helvetica,12"
set output out
set datafile separator ','

# time axis: seconds since the first sample
stats csv skip 1 using 1 nooutput
t0 = STATS_min

set grid
set key off
set multiplot layout 1,2

# Left: DS18B20 temperature over time
set title "DS18B20 temperature"
set xlabel "Time (s)"
set ylabel "Temperature (°C)"
plot csv skip 1 using (($1 - t0) / 1000.0):2 with linespoints pt 7 ps 0.6 lw 2

# Right: thermistor ADC vs DS18B20 temperature (calibration curve)
set title "NTC thermistor vs DS18B20"
set xlabel "DS18B20 temperature (°C)"
set ylabel "Thermistor ADC (0-1023)"
plot csv skip 1 using 2:4 with points pt 7 ps 0.8

unset multiplot
