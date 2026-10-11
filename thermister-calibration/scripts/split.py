"""Reads serial lines on stdin; echoes all, writes <base>.log (everything)
and <base>.csv (header + data rows only)."""
import re
import sys
import time

base = sys.argv[1]
HEADER = "time_ms,temp_c,temp_k,adc"
ROW = re.compile(r"^\d+,[^,]*,[^,]*,\d+$")
GRACE = 3.0  # seconds to wait for the post-reset header

log = open(base + ".log", "w")
csv = None
pending = []
start = time.time()

try:
  for raw in sys.stdin:
      line = raw.rstrip("\r\n")
      print(line, flush=True)
      log.write(line + "\n")
      log.flush()

      if csv is None:
          if line == HEADER:
              # Board reset when the port opened: earlier rows were stale.
              csv = open(base + ".csv", "w")
              csv.write(HEADER + "\n")
              pending = []
          elif ROW.match(line):
              pending.append(line)
          if csv is None and time.time() - start > GRACE:
              # No reset happened: the buffered rows are live, keep them.
              csv = open(base + ".csv", "w")
              csv.write(HEADER + "\n")
              csv.write("".join(r + "\n" for r in pending))
              pending = []
          if csv is not None:
              csv.flush()
      elif ROW.match(line):
          csv.write(line + "\n")
          csv.flush()
except KeyboardInterrupt:
  pass
