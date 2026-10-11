# Cross toolchain: arm-none-eabi-gcc shipped with the Seeeduino Arduino package.
set(ARDUINO15 "$ENV{HOME}/Library/Arduino15" CACHE PATH "Arduino15 data directory")
set(TOOLCHAIN_BIN "${ARDUINO15}/packages/Seeeduino/tools/arm-none-eabi-gcc/9-2019q4/bin")

set(CMAKE_SYSTEM_NAME Generic)
set(CMAKE_SYSTEM_PROCESSOR arm)
set(CMAKE_C_COMPILER   "${TOOLCHAIN_BIN}/arm-none-eabi-gcc")
set(CMAKE_CXX_COMPILER "${TOOLCHAIN_BIN}/arm-none-eabi-g++")
set(CMAKE_ASM_COMPILER "${TOOLCHAIN_BIN}/arm-none-eabi-gcc")
set(CMAKE_OBJCOPY      "${TOOLCHAIN_BIN}/arm-none-eabi-objcopy" CACHE FILEPATH "")
set(CMAKE_SIZE         "${TOOLCHAIN_BIN}/arm-none-eabi-size" CACHE FILEPATH "")
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)
