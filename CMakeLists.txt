cmake_minimum_required(VERSION 3.16)
project(PH3039 NONE)

set(FQBN "arduino:avr:uno" CACHE STRING "Board FQBN")
set(PORT "" CACHE STRING "Serial port (the Makefile auto-detects it)")
set(BAUD 9600 CACHE STRING "Monitor baud rate")

find_program(ARDUINO_CLI arduino-cli REQUIRED)

# arduino-cli wants <name>/<name>.ino, so stage src/main.cpp as a sketch.
set(SKETCH_DIR ${CMAKE_BINARY_DIR}/sketch)
set(SKETCH_INO ${SKETCH_DIR}/sketch.ino)
file(GLOB SRC_FILES CONFIGURE_DEPENDS ${CMAKE_SOURCE_DIR}/src/*)

add_custom_command(
  OUTPUT ${SKETCH_INO}
  COMMAND ${CMAKE_COMMAND} -E make_directory ${SKETCH_DIR}
  COMMAND ${CMAKE_COMMAND} -E copy_directory ${CMAKE_SOURCE_DIR}/src ${SKETCH_DIR}
  COMMAND ${CMAKE_COMMAND} -E rename ${SKETCH_DIR}/main.cpp ${SKETCH_INO}
  DEPENDS ${SRC_FILES}
)

add_custom_target(build ALL
  COMMAND ${ARDUINO_CLI} compile --fqbn ${FQBN} --build-path ${CMAKE_BINARY_DIR}/out ${SKETCH_DIR}
  DEPENDS ${SKETCH_INO}
  USES_TERMINAL
)

add_custom_target(upload
  COMMAND ${ARDUINO_CLI} compile --fqbn ${FQBN} --build-path ${CMAKE_BINARY_DIR}/out
          --upload --port ${PORT} ${SKETCH_DIR}
  DEPENDS ${SKETCH_INO}
  USES_TERMINAL
)

add_custom_target(monitor
  COMMAND ${ARDUINO_CLI} monitor --port ${PORT} --config baudrate=${BAUD}
  USES_TERMINAL
)
