# Builds the Seeed nRF52 Arduino core + needed libraries as a static lib `xiao_core`
# for the XIAO nRF52840 Sense, so plain C++ (setup()/loop()) can be built with CMake.
set(BSP_VERSION 1.1.13)
set(PKG  "${ARDUINO15}/packages/Seeeduino")
set(BSP  "${PKG}/hardware/nrf52/${BSP_VERSION}")
set(CORE "${BSP}/cores/nRF5")
set(VARIANT "${BSP}/variants/Seeed_XIAO_nRF52840_Sense")
set(CMSIS "${PKG}/tools/CMSIS/5.7.0/CMSIS")
set(TUSB "${BSP}/libraries/Adafruit_TinyUSB_Arduino/src")
set(LSM6DS3_DIR "$ENV{HOME}/Documents/Arduino/libraries/Seeed_Arduino_LSM6DS3" CACHE PATH "Seeed Arduino LSM6DS3 library")

foreach(p "${BSP}" "${LSM6DS3_DIR}/LSM6DS3.cpp")
  if(NOT EXISTS "${p}")
    message(FATAL_ERROR "Missing ${p}\n  arduino-cli core install Seeeduino:nrf52\n  arduino-cli lib install \"Seeed Arduino LSM6DS3\"")
  endif()
endforeach()

set(CPU_FLAGS -mcpu=cortex-m4 -mthumb -mfloat-abi=hard -mfpu=fpv4-sp-d16)

file(GLOB CORE_SRC
  "${CORE}/*.c" "${CORE}/*.cpp" "${CORE}/*.S"
  "${CORE}/avr/*.c" "${CORE}/utility/*.c" "${CORE}/utility/*.cpp"
  "${CORE}/linker/*.S"
  "${CORE}/sysview/*/*.c" "${CORE}/sysview/*/*.S"
  "${CORE}/nordic/nrfx/mdk/system_nrf52*.c" "${CORE}/nordic/nrfx/soc/nrfx_atomic.c"
  "${CORE}/nordic/nrfx/drivers/src/*.c" "${CORE}/nordic/nrfx/drivers/src/prs/*.c"
  "${CORE}/freertos/Source/*.c" "${CORE}/freertos/portable/GCC/nrf52/*.c"
  "${CORE}/freertos/portable/CMSIS/nrf52/*.c" "${CORE}/freertos/Source/portable/MemMang/heap_3.c")
file(GLOB TUSB_SRC
  "${TUSB}/arduino/*.cpp" "${TUSB}/arduino/*/*.cpp" "${TUSB}/arduino/ports/*/*.cpp"
  "${TUSB}/class/*/*.c" "${TUSB}/common/*.c" "${TUSB}/device/*.c"
  "${TUSB}/portable/nordic/nrf5x/*.c" "${TUSB}/tusb.c")
file(GLOB_RECURSE TUSB_PORT_ALL "${TUSB}/portable/*.c")
set(LIB_SRC
  "${BSP}/libraries/Wire/Wire_nRF52.cpp"
  "${BSP}/libraries/SPI/SPI.cpp" "${BSP}/libraries/SPI/SPI_nrf52832.cpp"
  "${LSM6DS3_DIR}/LSM6DS3.cpp")

# Core goes in an archive (like Arduino's core.a); TinyUSB + libraries are linked as plain
# objects so their hooks (USB init, ISRs) are never dropped by the archive linker.
add_library(xiao_core STATIC ${CORE_SRC} "${VARIANT}/variant.cpp")
add_library(xiao_libs OBJECT ${TUSB_SRC} ${LIB_SRC})

foreach(t xiao_core xiao_libs)
target_compile_definitions(${t} PUBLIC
  F_CPU=64000000 ARDUINO=10607 ARDUINO_Seeed_XIAO_nRF52840_Sense ARDUINO_ARCH_NRF52
  "ARDUINO_BSP_VERSION=\"${BSP_VERSION}\"" NRF52840_XXAA USBCON USE_TINYUSB
  USB_VID=0x2886 USB_PID=0x8045 "USB_MANUFACTURER=\"Seeed\"" "USB_PRODUCT=\"XIAO nRF52840 Sense\""
  SOFTDEVICE_PRESENT ARDUINO_NRF52_ADAFRUIT NRF52_SERIES DX_CC_TEE LFS_NAME_MAX=64
  CFG_DEBUG=0 CFG_LOGGER=0 CFG_SYSVIEW=0)

target_include_directories(${t} SYSTEM PUBLIC
  "${CMSIS}/Core/Include" "${CMSIS}/DSP/Include"
  "${CORE}/nordic" "${CORE}/nordic/nrfx" "${CORE}/nordic/nrfx/hal" "${CORE}/nordic/nrfx/mdk"
  "${CORE}/nordic/nrfx/soc" "${CORE}/nordic/nrfx/drivers/include" "${CORE}/nordic/nrfx/drivers/src"
  "${CORE}/nordic/softdevice/s140_nrf52_7.3.0_API/include"
  "${CORE}/nordic/softdevice/s140_nrf52_7.3.0_API/include/nrf52"
  "${CORE}/freertos/Source/include" "${CORE}/freertos/config"
  "${CORE}/freertos/portable/GCC/nrf52" "${CORE}/freertos/portable/CMSIS/nrf52"
  "${CORE}/sysview/SEGGER" "${CORE}/sysview/Config"
  "${TUSB}/arduino" "${CORE}" "${VARIANT}"
  "${LSM6DS3_DIR}" "${BSP}/libraries/Wire" "${BSP}/libraries/SPI" "${TUSB}")

target_compile_options(${t} PUBLIC ${CPU_FLAGS} -Ofast -g -ffunction-sections -fdata-sections -nostdlib -w
  $<$<COMPILE_LANGUAGE:CXX>:-std=gnu++11 -fno-rtti -fno-exceptions -fno-threadsafe-statics --param=max-inline-insns-single=500>)

endforeach()

target_link_options(xiao_core PUBLIC ${CPU_FLAGS} -Ofast -Wl,--gc-sections
  "-L${CORE}/linker" -Tnrf52840_s140_v7.ld -Wl,--wrap=malloc -Wl,--wrap=free
  --specs=nano.specs --specs=nosys.specs -u _printf_float)
target_link_directories(xiao_core PUBLIC "${CMSIS}/DSP/Lib/GCC")

# Link-time helper: wrap the core in a group so link order doesn't matter, then libs.
function(xiao_add_firmware target)
  add_executable(${target} ${ARGN} $<TARGET_OBJECTS:xiao_libs>)
  target_link_libraries(${target} PRIVATE -Wl,--start-group xiao_core arm_cortexM4lf_math m -Wl,--end-group)
  set_target_properties(${target} PROPERTIES SUFFIX ".elf")
  add_custom_command(TARGET ${target} POST_BUILD
    COMMAND ${CMAKE_OBJCOPY} -O ihex $<TARGET_FILE:${target}> ${target}.hex
    COMMAND ${BSP}/tools/adafruit-nrfutil/macos/adafruit-nrfutil dfu genpkg
            --dev-type 0x0052 --sd-req 0x0123 --application ${target}.hex ${target}.zip
    COMMAND ${CMAKE_SIZE} $<TARGET_FILE:${target}>
    WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR})
  set(FLASH_PORT "/dev/cu.usbmodem101" CACHE STRING "Serial port of the board")
  add_custom_target(flash
    COMMAND ${BSP}/tools/adafruit-nrfutil/macos/adafruit-nrfutil --verbose dfu serial
            --package ${target}.zip -p ${FLASH_PORT} -b 115200 --singlebank --touch 1200
    WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR} DEPENDS ${target} USES_TERMINAL)
endfunction()
