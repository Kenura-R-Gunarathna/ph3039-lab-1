cmake_minimum_required(VERSION 3.16)

# Cross-compile for the Seeed XIAO nRF52840 Sense (see cmake/).
set(CMAKE_TOOLCHAIN_FILE "${CMAKE_CURRENT_SOURCE_DIR}/cmake/toolchain.cmake" CACHE FILEPATH "")
project(dsp_and_fft LANGUAGES C CXX ASM)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)  # build/compile_commands.json for clangd

include(cmake/xiao_nrf52840.cmake)
# Pick the app:  cmake -DAPP=voice_dsp   (or: make APP=voice_dsp)
#   blink_demo | voice_dsp | voice_tflm | voice_edge_impulse
set(APP blink_demo CACHE STRING "Which apps/<name> to build")
if(NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/apps/${APP}/main.cpp")
  message(FATAL_ERROR "No apps/${APP}/main.cpp")
endif()
include_directories(common)
file(GLOB COMMON_SRC common/*.cpp)
xiao_add_firmware(${APP} apps/${APP}/main.cpp ${COMMON_SRC})
