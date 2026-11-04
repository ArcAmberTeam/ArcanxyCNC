cmake_minimum_required(VERSION 3.22)
find_program(CARGO_EXECUTABLE cargo REQUIRED)
set(account_target "${CMAKE_CURRENT_BINARY_DIR}/cargo")
set(account_binary "${account_target}/release/cnc-maint-account")
file(GLOB_RECURSE account_sources CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/src/*.rs")
add_custom_command(OUTPUT "${account_binary}"
    COMMAND "${CMAKE_COMMAND}" -E env "CARGO_TARGET_DIR=${account_target}"
        "${CARGO_EXECUTABLE}" build --release --locked
    WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
    DEPENDS ${account_sources} Cargo.toml Cargo.lock rust-toolchain.toml
    VERBATIM)
add_custom_target(betterlinuxcnc-maintenance-account ALL DEPENDS "${account_binary}")
install(PROGRAMS "${account_binary}"
    DESTINATION "${CMAKE_INSTALL_LIBDIR}/betterlinuxcnc/account-management/cnc-maint")
