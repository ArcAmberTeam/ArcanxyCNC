cmake_minimum_required(VERSION 3.22)
file(GLOB_RECURSE error_record_client_sources CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/../error-records/client/src/*.rs")
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
    project(BetterLinuxCNCCamLink LANGUAGES NONE)
    include("${CMAKE_CURRENT_SOURCE_DIR}/../../../cmake/ApplicationInstall.cmake")
endif()

set(BETTERCNC_CAM_LINK_BINARY "" CACHE FILEPATH "Prebuilt CAM Link binary for the target architecture")
if(BETTERCNC_CAM_LINK_BINARY)
    if(NOT EXISTS "${BETTERCNC_CAM_LINK_BINARY}")
        message(FATAL_ERROR "BETTERCNC_CAM_LINK_BINARY does not exist")
    endif()
    set(cam_link_binary "${BETTERCNC_CAM_LINK_BINARY}")
else()
    find_program(CARGO_EXECUTABLE cargo REQUIRED)
    set(cam_link_target "${CMAKE_CURRENT_BINARY_DIR}/cargo")
    set(cam_link_binary "${cam_link_target}/release/betterlinuxcnc-cam-link")
    file(GLOB_RECURSE service_sources CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/src/*.rs")
    add_custom_command(OUTPUT "${cam_link_binary}"
        COMMAND "${CMAKE_COMMAND}" -E env "CARGO_TARGET_DIR=${cam_link_target}"
            "${CARGO_EXECUTABLE}" build --release --locked --bin betterlinuxcnc-cam-link
        WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
        DEPENDS ${error_record_client_sources} ${service_sources} Cargo.toml Cargo.lock rust-toolchain.toml
        VERBATIM)
    add_custom_target(betterlinuxcnc-system-services ALL DEPENDS "${cam_link_binary}")
endif()
install(PROGRAMS "${cam_link_binary}" DESTINATION ${CMAKE_INSTALL_BINDIR})
