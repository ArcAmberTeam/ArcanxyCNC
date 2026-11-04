cmake_minimum_required(VERSION 3.22)
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
    project(BetterLinuxCNCUpdater LANGUAGES NONE)
    include("${CMAKE_CURRENT_SOURCE_DIR}/../../../cmake/ApplicationInstall.cmake")
endif()

set(BETTERCNC_UPDATER_BINARY "" CACHE FILEPATH "Prebuilt release updater for the target architecture")
if(BETTERCNC_UPDATER_BINARY)
    if(NOT EXISTS "${BETTERCNC_UPDATER_BINARY}")
        message(FATAL_ERROR "BETTERCNC_UPDATER_BINARY does not exist")
    endif()
    set(updater_binary "${BETTERCNC_UPDATER_BINARY}")
else()
    find_program(CARGO_EXECUTABLE cargo REQUIRED)
    set(updater_target "${CMAKE_CURRENT_BINARY_DIR}/cargo")
    set(updater_binary "${updater_target}/release/betterlinuxcnc-updater")
    file(GLOB_RECURSE updater_sources CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/src/*.rs")
    file(GLOB_RECURSE local_update_sources CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/../local-update/src/*.rs")
    add_custom_command(OUTPUT "${updater_binary}"
        COMMAND "${CMAKE_COMMAND}" -E env "CARGO_TARGET_DIR=${updater_target}"
            "${CARGO_EXECUTABLE}" build --release --locked --bin betterlinuxcnc-updater
        WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
        DEPENDS ${updater_sources} ${local_update_sources} ../local-update/Cargo.toml src/updater/package_members.py Cargo.toml Cargo.lock rust-toolchain.toml
        VERBATIM)
    add_custom_target(betterlinuxcnc-updater-service ALL DEPENDS "${updater_binary}")
endif()
install(PROGRAMS "${updater_binary}" DESTINATION ${CMAKE_INSTALL_BINDIR})

configure_file(packaging/betterlinuxcnc-system-update.service.in betterlinuxcnc-system-update.service @ONLY)
configure_file(packaging/49-betterlinuxcnc-update.rules.in 49-betterlinuxcnc-update.rules @ONLY)
install(FILES "${CMAKE_CURRENT_BINARY_DIR}/betterlinuxcnc-system-update.service"
    DESTINATION "${CMAKE_INSTALL_PREFIX}/lib/systemd/system")
install(FILES "${CMAKE_CURRENT_BINARY_DIR}/49-betterlinuxcnc-update.rules"
    DESTINATION "${CMAKE_INSTALL_DATADIR}/polkit-1/rules.d")
# Direct CMake installs preserve local policy; Debian upgrades use the conffile entry.
install(CODE "
    if(NOT EXISTS \"\$ENV{DESTDIR}/etc/betterlinuxcnc/updater.json\")
        file(INSTALL DESTINATION \"/etc/betterlinuxcnc\"
            TYPE FILE FILES \"${CMAKE_CURRENT_SOURCE_DIR}/packaging/updater.json\")
    endif()
")
