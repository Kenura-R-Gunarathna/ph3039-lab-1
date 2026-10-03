BUILD := build

# Works on Linux, macOS and Windows (Git Bash / MSYS2 / WSL with make).
# Python 3 launcher: python3 (Linux/macOS), python or py (Windows).
PY := $(shell command -v python3 || command -v python || command -v py)
# Serial port: auto-detected; override with `make upload PORT=/dev/ttyACM0` (or COM3).
PORT ?= $(shell $(PY) scripts/port.py)
export PORT

.PHONY: configure build upload monitor run log plot clean
configure:
	cmake -S . -B $(BUILD)
build: configure
	cmake --build $(BUILD)
upload: configure
	cmake -S . -B $(BUILD) -DPORT=$(PORT)
	cmake --build $(BUILD) --target upload
monitor: configure
	cmake -S . -B $(BUILD) -DPORT=$(PORT)
	cmake --build $(BUILD) --target monitor
clean:
	rm -rf $(BUILD)
run:
	$(MAKE) build
	$(MAKE) upload
	$(MAKE) log

# Log serial: data/log_<stamp>.log (everything) + .csv (data rows only)
log: configure
	@test -n "$(PORT)" || exit 1
	./scripts/log.sh $(PORT) 9600

# Live plot of the newest CSV -> data/plot.png (run alongside `make log`)
plot:
	./scripts/plot.sh $(CSV)
