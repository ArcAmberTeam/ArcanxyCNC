cmake_minimum_required(VERSION 3.22)
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
    project(BetterLinuxCNCController VERSION 0.2.0 LANGUAGES NONE)
    include("${CMAKE_CURRENT_SOURCE_DIR}/../../cmake/ApplicationInstall.cmake")
    include(CTest)
endif()

find_package(Python3 3.11 REQUIRED COMPONENTS Interpreter)
configure_file(packaging/betterlinuxcnc-service.in betterlinuxcnc-service @ONLY)
install(PROGRAMS "${CMAKE_CURRENT_BINARY_DIR}/betterlinuxcnc-service" DESTINATION ${CMAKE_INSTALL_BINDIR})
# The Rust CAM CLI replaces this retired Python package during upgrades.
install(CODE "file(REMOVE_RECURSE \"\$ENV{DESTDIR}${CMAKE_INSTALL_FULL_LIBDIR}/betterlinuxcnc/python/bettercnc_cam_link\")")
install(DIRECTORY src/ DESTINATION ${CMAKE_INSTALL_LIBDIR}/betterlinuxcnc/python
    PATTERN "__pycache__" EXCLUDE PATTERN "*.pyc" EXCLUDE PATTERN "*.egg-info" EXCLUDE)

if(BUILD_TESTING)
    add_test(NAME backend-integration COMMAND Python3::Interpreter -m unittest discover
        -s "${CMAKE_CURRENT_SOURCE_DIR}/tests" -v)
    set_tests_properties(backend-integration PROPERTIES ENVIRONMENT
        "PYTHONPATH=${CMAKE_CURRENT_SOURCE_DIR}/src")
    set_property(TEST backend-integration APPEND PROPERTY ENVIRONMENT_MODIFICATION
        "PYTHONPATH=path_list_prepend:${CMAKE_CURRENT_SOURCE_DIR}/../platform/error-records/python/src")
endif()
