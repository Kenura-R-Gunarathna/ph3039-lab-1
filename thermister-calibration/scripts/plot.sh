#!/bin/sh
# Usage: plot.sh [csv] [--once]
# Redraws data/plot.png from the newest CSV every 2 s (Ctrl+C to stop).
# Time axis = (time_ms - first) / 1000 at plot time; the CSV keeps raw ms.
here=$(dirname "$0")
csv=""; once=0
for a in "$@"; do
  case "$a" in --once) once=1 ;; *) csv="$a" ;; esac
done
[ -n "$csv" ] || csv=$(ls -t data/*.csv 2>/dev/null | head -1)
[ -n "$csv" ] || { echo "No CSV in data/ yet. Run 'make log' first."; exit 1; }
out=data/plot.png

draw() {
  # need a header plus at least one real reading
  [ "$(grep -cE '^[0-9]+,[0-9.-]+,' "$csv")" -ge 1 ] || return 0
  gnuplot -c "$here/plot.gp" "$csv" "$out" 2>/dev/null
}
finish() { draw; echo; echo "Final plot: $out (from $csv)"; }

if [ "$once" = 1 ]; then finish; exit 0; fi
trap finish EXIT
trap 'exit 130' INT TERM HUP
echo "Plotting $csv -> $out every 2 s (Ctrl+C to stop)"
while true; do draw; sleep 2; done
