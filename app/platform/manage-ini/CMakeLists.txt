cmake_minimum_required(VERSION 3.22)
file(GLOB_RECURSE error_record_client_sources CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/../error-records/client/src/*.rs")
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
    project(BetterLinuxCNCManageIni LANGUAGES NONE)
    include("${CMAKE_CURRENT_SOURCE_DIR}/../../../cmake/ApplicationInstall.cmake")
endif()

find_program(CARGO_EXECUTABLE cargo REQUIRED)
set(pa_target "${CMAKE_CURRENT_BINARY_DIR}/cargo")
set(pa_binary "${pa_target}/release/pa")
set(pa_helper "${pa_target}/release/pa-config")
file(GLOB_RECURSE pa_sources CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/src/*.rs")
add_custom_command(OUTPUT "${pa_binary}" "${pa_helper}"
    COMMAND "${CMAKE_COMMAND}" -E env "CARGO_TARGET_DIR=${pa_target}"
        "${CARGO_EXECUTABLE}" build --release --locked --bins
    WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
    DEPENDS ${error_record_client_sources} ${pa_sources} Cargo.toml Cargo.lock rust-toolchain.toml
    VERBATIM)
add_custom_target(betterlinuxcnc-management-terminal ALL DEPENDS "${pa_binary}" "${pa_helper}")
install(PROGRAMS "${pa_binary}" DESTINATION ${CMAKE_INSTALL_BINDIR})

install(PROGRAMS "${pa_helper}" DESTINATION "${CMAKE_INSTALL_LIBDIR}/betterlinuxcnc/manage-ini")
