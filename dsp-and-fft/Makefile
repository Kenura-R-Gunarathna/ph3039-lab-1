# Thin wrapper around CMake/Ninja.   make [build|flash|monitor|clean]
BUILD ?= build
PORT  ?= /dev/cu.usbmodem101

.PHONY: all build configure flash monitor clean
all: build

configure:
	cmake -S . -B $(BUILD) -G Ninja -DFLASH_PORT=$(PORT)

$(BUILD)/build.ninja:
	$(MAKE) configure

build: $(BUILD)/build.ninja
	cmake --build $(BUILD)

# Double-tap reset first if the board isn't running a sketch with a 1200-baud touch.
flash: build
	cmake --build $(BUILD) --target flash

monitor:
	arduino-cli monitor -p $(PORT) -c baudrate=115200

clean:
	rm -rf $(BUILD)
