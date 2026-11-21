cmake_minimum_required(VERSION 3.22)
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
    project(BetterLinuxCNCSession VERSION 26.11.21.2 LANGUAGES NONE)
    include("${CMAKE_CURRENT_SOURCE_DIR}/../../cmake/ApplicationInstall.cmake")
    message(STATUS "Installing the headless session client only")
endif()
find_package(Python3 3.11 REQUIRED COMPONENTS Interpreter)
configure_file(app/betterlinuxcnc.in betterlinuxcnc @ONLY)

if(CMAKE_SYSTEM_NAME STREQUAL "Linux" AND NOT CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
    find_program(DESKTOP_NODE NAMES node REQUIRED)
    find_program(DESKTOP_NPM NAMES npm REQUIRED)
    get_filename_component(node_dir "${DESKTOP_NODE}" DIRECTORY)
    set(web "${CMAKE_CURRENT_SOURCE_DIR}/web")
    set(stage "${CMAKE_CURRENT_BINARY_DIR}/frontend")
    set(bundle "${stage}/app/desktop/web/release/linux-unpacked")
    file(GLOB_RECURSE desktop_inputs CONFIGURE_DEPENDS
        "${web}/src/*" "${web}/electron/*" "${web}/scripts/*" "${web}/public/*")
    file(GLOB desktop_config CONFIGURE_DEPENDS
        "${web}/*.json" "${web}/*.ts" "${web}/*.html" "${web}/SHADCN-LICENSE")
    set(version_manifest "${CMAKE_CURRENT_SOURCE_DIR}/../../versions/version.json")
    add_custom_command(OUTPUT "${stage}/packaged.stamp"
        COMMAND "${CMAKE_COMMAND}" -E env "PATH=${node_dir}:$ENV{PATH}"
            "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/package_web.py"
            "${web}" "${stage}" "${DESKTOP_NPM}"
        COMMAND "${CMAKE_COMMAND}" -E touch "${stage}/packaged.stamp"
        DEPENDS ${desktop_inputs} ${desktop_config} "${version_manifest}"
            "${CMAKE_CURRENT_SOURCE_DIR}/LICENSE" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/package_web.py"
        VERBATIM)
    add_custom_target(betterlinuxcnc-desktop-bundle ALL DEPENDS "${stage}/packaged.stamp")
    install(DIRECTORY "${bundle}/" DESTINATION "${CMAKE_INSTALL_LIBDIR}/betterlinuxcnc/desktop"
        PATTERN "chrome-sandbox" EXCLUDE
        PATTERN "betterlinuxcnc-desktop" PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE
        PATTERN "chrome_crashpad_handler" PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE)
endif()

install(PROGRAMS "${CMAKE_CURRENT_BINARY_DIR}/betterlinuxcnc" DESTINATION ${CMAKE_INSTALL_BINDIR})
install(DIRECTORY python/bettercnc DESTINATION "${CMAKE_INSTALL_LIBDIR}/betterlinuxcnc/python"
    PATTERN "__pycache__" EXCLUDE PATTERN "*.pyc" EXCLUDE PATTERN "*.md" EXCLUDE)
install(FILES LICENSE DESTINATION "${CMAKE_INSTALL_DATADIR}/doc/betterlinuxcnc" RENAME COPYING)
