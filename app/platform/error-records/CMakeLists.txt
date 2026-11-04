find_program(CARGO_EXECUTABLE cargo REQUIRED)
find_package(Python3 3.11 REQUIRED COMPONENTS Interpreter)
set(module_target "${CMAKE_CURRENT_BINARY_DIR}/cargo")
set(module_binary "${module_target}/release/betterlinuxcnc-error-records")
file(GLOB_RECURSE module_sources CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/src/*.rs" "${CMAKE_CURRENT_SOURCE_DIR}/client/src/*.rs")
add_custom_command(OUTPUT "${module_binary}"
    COMMAND "${CMAKE_COMMAND}" -E env "CARGO_TARGET_DIR=${module_target}" "${CARGO_EXECUTABLE}" build --release --locked
    WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
    DEPENDS ${module_sources} Cargo.toml Cargo.lock client/Cargo.toml rust-toolchain.toml VERBATIM)
add_custom_command(OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/runtime/ready"
    COMMAND Python3::Interpreter "${CMAKE_CURRENT_SOURCE_DIR}/runtime/prepare.py" "${CMAKE_CURRENT_BINARY_DIR}/runtime"
    DEPENDS runtime/prepare.py runtime/mysql.json VERBATIM)
add_custom_target(betterlinuxcnc-error-records-binary ALL DEPENDS "${module_binary}" "${CMAKE_CURRENT_BINARY_DIR}/runtime/ready")
install(PROGRAMS "${module_binary}" DESTINATION "${CMAKE_INSTALL_LIBDIR}/betterlinuxcnc/error-records")
install(DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/runtime/mysql" DESTINATION "${CMAKE_INSTALL_LIBDIR}/betterlinuxcnc/error-records")
install(FILES packaging/betterlinuxcnc-error-records.service DESTINATION "${CMAKE_INSTALL_LIBDIR}/betterlinuxcnc/error-records")
