# Thin wrapper around CMake/Ninja.   make [build|flash|monitor|clean] [PORT=/dev/cu.usbmodemXXXX]
# APP = blink_demo | audio_capture | voice_dsp | voice_cnn | voice_tflm | voice_edge_impulse (each gets its own build dir)
APP   ?= blink_demo
BUILD ?= build/$(APP)
# Auto-detect the board (the usbmodem number changes with the USB port used).
PORT  ?= $(firstword $(wildcard /dev/cu.usbmodem*))

.PHONY: all build configure flash monitor clean check-port
all: build

configure:
	cmake -S . -B $(BUILD) -G Ninja -DAPP=$(APP)

$(BUILD)/build.ninja:
	$(MAKE) configure

build: $(BUILD)/build.ninja
	cmake --build $(BUILD)

check-port:
	@test -n "$(PORT)" || { echo "No /dev/cu.usbmodem* found - is the board plugged in? (or pass PORT=...)"; exit 1; }
	@echo "Using port $(PORT)"

# Double-tap reset first if the board isn't running a sketch with a 1200-baud touch.
flash: build check-port
	cmake -S . -B $(BUILD) -DAPP=$(APP) -DFLASH_PORT=$(PORT) > /dev/null
	cmake --build $(BUILD) --target flash

monitor: check-port
	arduino-cli monitor -p $(PORT) -c baudrate=115200

clean:
	rm -rf build
