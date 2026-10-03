# PH3039 – Data Acquisition Lab

Arduino Uno temperature logger. It reads a **DS18B20** digital sensor and an
**NTC thermistor** (analog), streams them over serial, saves each run to CSV,
and plots the thermistor calibration curve against the DS18B20.

## Hardware

| Part | Connection |
|------|------------|
| DS18B20 (1-Wire) | digital pin `2` |
| NTC thermistor | analog pin `A2` |
| Board | Arduino Uno (`arduino:avr:uno`), serial at 9600 baud |

## Layout

```
src/main.cpp      sketch (staged as a .ino by CMake)
src/fmt.h         tiny "{}" formatter for Serial
scripts/log.sh    serial -> data/log_<stamp>.log + .csv
scripts/split.py  splits serial output into full log and CSV data rows
scripts/plot.sh   redraws data/plot.png from the newest CSV
scripts/plot.gp   gnuplot script (temperature vs time, ADC vs temperature)
scripts/port.py   auto-detects the Arduino's serial port
data/             all logs, kept in git on every branch
```

## Requirements

`arduino-cli` (with the `arduino:avr` core), `cmake`, `make`, `python3`,
`gnuplot`.

- **macOS / Linux:** works in a normal terminal.
- **Windows:** use Git Bash, MSYS2 or WSL; the scripts are shell scripts.

## Usage

```sh
make build      # compile
make upload     # flash the board
make monitor    # live serial monitor
make log        # log serial to data/log_<stamp>.{log,csv} (Ctrl+C to stop)
make plot       # plot newest CSV -> data/plot.png (run alongside `make log`)
make run        # build + upload + log
make clean
```

The serial port is auto-detected. To override it:

```sh
make upload PORT=/dev/ttyACM0     # Linux
make log    PORT=/dev/cu.usbmodem101   # macOS
make log    PORT=COM3             # Windows
```

Plot a specific file with `make plot CSV=data/log_YYYYMMDD_HHMMSS.csv`.

## Data

Each `make log` run creates two files in `data/`:

- `log_<stamp>.log`: every serial line, including `#` error lines
- `log_<stamp>.csv`: header and data rows only, `time_ms,temp_c,temp_k,adc`

Filenames are timestamped, so logs from different machines and branches merge
without conflicts. Don't delete or rewrite files in `data/`.

## Branches

`main` is cross-platform (Linux, macOS, Windows). Other branches (`Linux`,
`Linux_Analysis`, `TSS`) can be updated with `git merge main`.
