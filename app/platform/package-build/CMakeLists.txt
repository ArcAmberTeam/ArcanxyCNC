cmake_minimum_required(VERSION 3.22)
find_program(CARGO_EXECUTABLE cargo REQUIRED)
set(module_target "${CMAKE_CURRENT_BINARY_DIR}/cargo")
set(module_binary "${module_target}/release/betterlinuxcnc-package-build")
file(GLOB_RECURSE module_sources CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/src/*.rs")
add_custom_command(OUTPUT "${module_binary}"
    COMMAND "${CMAKE_COMMAND}" -E env "CARGO_TARGET_DIR=${module_target}"
        "${CARGO_EXECUTABLE}" build --release --locked
    WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
    DEPENDS ${module_sources} Cargo.toml Cargo.lock rust-toolchain.toml
    VERBATIM)
add_custom_target(betterlinuxcnc-package-build-binary ALL DEPENDS "${module_binary}")
install(PROGRAMS "${module_binary}" DESTINATION "${CMAKE_INSTALL_LIBDIR}/betterlinuxcnc/package-build")
