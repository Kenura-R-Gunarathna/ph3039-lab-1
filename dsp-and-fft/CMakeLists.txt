cmake_minimum_required(VERSION 3.16)

# Cross-compile for the Seeed XIAO nRF52840 Sense (see cmake/).
set(CMAKE_TOOLCHAIN_FILE "${CMAKE_CURRENT_SOURCE_DIR}/cmake/toolchain.cmake" CACHE FILEPATH "")
project(dsp_and_fft LANGUAGES C CXX ASM)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)  # build/compile_commands.json for clangd

include(cmake/xiao_nrf52840.cmake)
xiao_add_firmware(dsp_and_fft src/main.cpp)
