#!/bin/sh
# Usage: log.sh <port> <baud>
# Console shows everything. data/<stamp>.log gets every line,
# data/<stamp>.csv gets only the header and data rows.
mkdir -p data
base=data/log_$(date +%Y%m%d_%H%M%S)

# Safe exit: runs on Ctrl+C, kill, or the board being unplugged.
finish() {
  echo
  if [ -f "$base.csv" ]; then
    rows=$(( $(wc -l < "$base.csv") - 1 ))
    errs=$(grep -c '^#' "$base.log")
    echo "Saved $rows data rows, $errs error lines"
    echo "  $base.csv"
    echo "  $base.log"
  else
    echo "No data rows received. Check the port and that the board is running."
    echo "  $base.log (raw output, if any)"
  fi
}
trap finish EXIT
trap 'exit 130' INT TERM HUP

echo "Logging to $base.log and $base.csv (Ctrl+C to stop)"
arduino-cli monitor --quiet --port "$1" --config baudrate="$2" \
| "${PYTHON:-$(command -v python3 || command -v python || command -v py)}" "$(dirname "$0")/split.py" "$base"
