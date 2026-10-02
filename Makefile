BUILD := build

.PHONY: configure build upload monitor run log plot clean
configure:
	cmake -S . -B $(BUILD)
build: configure
	cmake --build $(BUILD)
upload: configure
	cmake --build $(BUILD) --target upload
monitor: configure
	cmake --build $(BUILD) --target monitor
clean:
	rm -rf $(BUILD)
run:
	$(MAKE) build
	$(MAKE) upload
	$(MAKE) log

# Log serial: data/log_<stamp>.log (everything) + .csv (data rows only)
log: configure
	./scripts/log.sh /dev/cu.usbmodem101 9600

# Live plot of the newest CSV -> data/plot.png (run alongside `make log`)
plot:
	./scripts/plot.sh $(CSV)
