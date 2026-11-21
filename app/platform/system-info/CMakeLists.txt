cmake_minimum_required(VERSION 3.22)
find_program(CARGO_EXECUTABLE cargo REQUIRED)
set(system_info_target "${CMAKE_CURRENT_BINARY_DIR}/cargo")
set(system_info_binary "${system_info_target}/release/betterlinuxcnc-system-info")
file(GLOB_RECURSE system_info_sources CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/src/*.rs")
add_custom_command(OUTPUT "${system_info_binary}"
    COMMAND "${CMAKE_COMMAND}" -E env "CARGO_TARGET_DIR=${system_info_target}"
        "${CARGO_EXECUTABLE}" build --release --locked --bins
    WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
    DEPENDS ${system_info_sources} Cargo.toml Cargo.lock rust-toolchain.toml
    VERBATIM)
add_custom_target(betterlinuxcnc-system-information ALL DEPENDS "${system_info_binary}")
install(PROGRAMS "${system_info_binary}" DESTINATION "${CMAKE_INSTALL_LIBDIR}/betterlinuxcnc/system-info")
