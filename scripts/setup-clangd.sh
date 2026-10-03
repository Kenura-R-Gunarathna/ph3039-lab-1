```bash
#!/usr/bin/env bash
set -euo pipefail

# Detect common Arduino data directories on Linux and macOS.
ARDUINO_ROOTS=(
    "$HOME/.arduino15"
    "$HOME/Library/Arduino15"
)

# Find an installed Arduino AVR core.
AVR_CORE=""
for root in "${ARDUINO_ROOTS[@]}"; do
    for path in "$root"/packages/arduino/hardware/avr/*/cores/arduino; do
        if [[ -d "$path" ]]; then
            AVR_CORE="$path"
            break 2
        fi
    done
done

if [[ -z "$AVR_CORE" ]]; then
    echo "Error: Arduino AVR core not found."
    echo "Install Arduino AVR Boards using Arduino IDE or arduino-cli."
    exit 1
fi

AVR_VARIANT="$(dirname "$AVR_CORE")/variants/standard"

if [[ ! -d "$AVR_VARIANT" ]]; then
    echo "Error: Arduino Uno variant directory not found."
    exit 1
fi

# Find AVR compiler headers. Different installations can use
# different directory structures.
AVR_INCLUDE=""
for root in "${ARDUINO_ROOTS[@]}"; do
    for path in \
        "$root"/packages/arduino/tools/avr-gcc/*/avr/include \
        "$root"/packages/arduino/tools/avr-gcc/*/*/avr/include
    do
        if [[ -d "$path" ]]; then
            AVR_INCLUDE="$path"
            break 2
        fi
    done
done

if [[ -z "$AVR_INCLUDE" ]]; then
    echo "Error: AVR GCC headers not found."
    echo "Check that the Arduino AVR toolchain is installed."
    exit 1
fi

# Find the Arduino sketchbook libraries on Linux or macOS.
LIBRARY_ROOTS=(
    "$HOME/Arduino/libraries"
    "$HOME/Documents/Arduino/libraries"
)

find_library() {
    local library="$1"

    for root in "${LIBRARY_ROOTS[@]}"; do
        if [[ -d "$root/$library" ]]; then
            printf '%s\n' "$root/$library"
            return 0
        fi
    done

    return 1
}

# Generate .clangd.
{
    cat <<'EOF'
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
EOF

    printf '    - -I%s\n' "$AVR_CORE"
    printf '    - -I%s\n' "$AVR_VARIANT"
    printf '    - -I%s\n' "$AVR_INCLUDE"

    for library in OneWire DallasTemperature; do
        if library_path="$(find_library "$library")"; then
            printf '    - -I%s\n' "$library_path"
        else
            echo "Warning: $library library not found; skipping." >&2
        fi
    done

    cat <<'EOF'
  Remove:
    - -march=*
    - -mcpu=*

Diagnostics:
  Suppress:
    - pp_file_not_found_with_hint
EOF
} > .clangd

echo "Generated .clangd successfully."
echo "Arduino core: $AVR_CORE"
echo "AVR headers:  $AVR_INCLUDE"
echo "Configuration: $(pwd)/.clangd"
```