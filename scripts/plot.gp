# gnuplot -c plot.gp <csv> <png>
csv = ARG1
out = ARG2

set terminal png size 1000,500 font "Helvetica,12"
set output out
set datafile separator ','

# time axis: seconds since the first sample
stats csv skip 1 using 1 nooutput
t0 = STATS_min

set title "DS18B20 temperature"
set xlabel "Time (s)"
set ylabel "Temperature (°C)"
set grid
set key off
plot csv skip 1 using (($1 - t0) / 1000.0):2 with linespoints pt 7 ps 0.6 lw 2
