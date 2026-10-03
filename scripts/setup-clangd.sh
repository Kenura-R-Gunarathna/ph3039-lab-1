#!/usr/bin/env bash

set -e

echo "Setting up clangd..."

# --------------------------------------------------
# Find Arduino data directory
# --------------------------------------------------

if [ -d "$HOME/.arduino15" ]; then
    ARDUINO15="$HOME/.arduino15"
elif [ -d "$HOME/Library/Arduino15" ]; then
    ARDUINO15="$HOME/Library/Arduino15"
else
    echo "Error: Arduino15 directory not found."
    exit 1
fi

echo "Arduino15: $ARDUINO15"

# --------------------------------------------------
# Find Arduino AVR core
# --------------------------------------------------

AVR_CORE=$(find "$ARDUINO15/packages/arduino/hardware/avr" \
    -type d \
    -path "*/cores/arduino" \
    -print -quit)

if [ -z "$AVR_CORE" ]; then
    echo "Error: Arduino AVR core not found."
    exit 1
fi

AVR_ROOT=$(dirname "$AVR_CORE")

echo "AVR core: $AVR_CORE"

# --------------------------------------------------
# Find AVR GCC headers
# --------------------------------------------------

AVR_INCLUDE=$(find "$ARDUINO15/packages/arduino/tools/avr-gcc" \
    -type d \
    -path "*/avr/include" \
    -print -quit)

if [ -z "$AVR_INCLUDE" ]; then
    echo "Error: AVR GCC headers not found."
    exit 1
fi

echo "AVR headers: $AVR_INCLUDE"

# --------------------------------------------------
# Arduino libraries
# --------------------------------------------------

ONEWIRE="$HOME/Arduino/libraries/OneWire"
DALLAS="$HOME/Arduino/libraries/DallasTemperature"

# macOS can also use ~/Documents/Arduino
if [ ! -d "$ONEWIRE" ]; then
    ONEWIRE="$HOME/Documents/Arduino/libraries/OneWire"
fi

if [ ! -d "$DALLAS" ]; then
    DALLAS="$HOME/Documents/Arduino/libraries/DallasTemperature"
fi

# --------------------------------------------------
# Generate .clangd
# --------------------------------------------------

cat > .clangd <<EOF
CompileFlags:
  Compiler: clang++
  Add:
    - -xc++
    - -std=gnu++11
    - -D__AVR__
    - -D__AVR_ATmega328P__
    - -DARDUINO=10819
    - -DARDUINO_AVR_UNO
    - -DARDUINO_ARCH_AVR
    - -DF_CPU=16000000L

    - -I$AVR_CORE
    - -I$AVR_ROOT/variants/standard
    - -I$AVR_INCLUDE
EOF

if [ -d "$ONEWIRE" ]; then
    echo "    - -I$ONEWIRE" >> .clangd
    echo "OneWire: $ONEWIRE"
fi

if [ -d "$DALLAS" ]; then
    echo "    - -I$DALLAS" >> .clangd
    echo "DallasTemperature: $DALLAS"
fi

cat >> .clangd <<'EOF'

  Remove:
    - -march=*
    - -mcpu=*

Diagnostics:
  Suppress:
    - pp_file_not_found_with_hint
EOF

echo
echo "clangd configuration created:"
echo "  $(pwd)/.clangd"
echo
echo "Done."