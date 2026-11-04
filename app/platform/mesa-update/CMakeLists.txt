cmake_minimum_required(VERSION 3.22)
file(GLOB_RECURSE error_record_client_sources CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/../error-records/client/src/*.rs")
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
    project(BetterLinuxCNCMesaUpdate LANGUAGES NONE)
    include("${CMAKE_CURRENT_SOURCE_DIR}/../../../cmake/ApplicationInstall.cmake")
endif()

set(BETTERCNC_MESA_UPDATE_BINARY "" CACHE FILEPATH "Prebuilt Mesa release downloader for the target architecture")
set(BETTERCNC_MESA_FLASH_BINARY "" CACHE FILEPATH "Prebuilt independent Mesa root verifier for the target architecture")
if(BETTERCNC_MESA_UPDATE_BINARY OR BETTERCNC_MESA_FLASH_BINARY)
    if(NOT EXISTS "${BETTERCNC_MESA_UPDATE_BINARY}" OR NOT EXISTS "${BETTERCNC_MESA_FLASH_BINARY}")
        message(FATAL_ERROR "Both prebuilt Mesa binaries must exist")
    endif()
    set(mesa_update_binary "${BETTERCNC_MESA_UPDATE_BINARY}")
    set(mesa_flash_binary "${BETTERCNC_MESA_FLASH_BINARY}")
else()
    find_program(CARGO_EXECUTABLE cargo REQUIRED)
    set(mesa_target "${CMAKE_CURRENT_BINARY_DIR}/cargo")
    set(mesa_update_binary "${mesa_target}/release/betterlinuxcnc-mesa-update")
    set(mesa_flash_binary "${mesa_target}/release/betterlinuxcnc-mesa-flash")
    file(GLOB_RECURSE mesa_sources CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/src/*.rs")
    add_custom_command(OUTPUT "${mesa_update_binary}" "${mesa_flash_binary}"
        COMMAND "${CMAKE_COMMAND}" -E env "CARGO_TARGET_DIR=${mesa_target}"
            "${CARGO_EXECUTABLE}" build --release --locked --bins
        WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
        DEPENDS ${error_record_client_sources} ${mesa_sources} Cargo.toml Cargo.lock rust-toolchain.toml
        VERBATIM)
    add_custom_target(betterlinuxcnc-mesa-services ALL DEPENDS "${mesa_update_binary}" "${mesa_flash_binary}")
endif()
install(PROGRAMS "${mesa_update_binary}" "${mesa_flash_binary}" DESTINATION ${CMAKE_INSTALL_BINDIR})

foreach(unit betterlinuxcnc-mesa-update.service betterlinuxcnc-mesa-update.timer betterlinuxcnc-mesa-flash.service)
    configure_file("packaging/${unit}.in" "${unit}" @ONLY)
    install(FILES "${CMAKE_CURRENT_BINARY_DIR}/${unit}" DESTINATION "${CMAKE_INSTALL_PREFIX}/lib/systemd/system")
endforeach()
