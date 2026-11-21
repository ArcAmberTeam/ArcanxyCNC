cmake_minimum_required(VERSION 3.22)
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
    project(BetterLinuxCNCLauncher VERSION 0.1.0 LANGUAGES NONE)
    include("${CMAKE_CURRENT_SOURCE_DIR}/../../cmake/ApplicationInstall.cmake")
endif()

set(BETTERCNC_PROJECT_DIR "/etc/betterlinuxcnc" CACHE PATH "Runtime project directory containing launcher.json")
configure_file(packaging/betterlinuxcnc-launch.in betterlinuxcnc-launch @ONLY)
configure_file(packaging/betterlinuxcnc-launcher.service.in betterlinuxcnc-launcher.service @ONLY)
configure_file(packaging/betterlinuxcnc-autostart.desktop.in betterlinuxcnc-autostart.desktop @ONLY)
configure_file(packaging/betterlinuxcnc-kiosk.desktop.in betterlinuxcnc-kiosk.desktop @ONLY)
install(PROGRAMS "${CMAKE_CURRENT_BINARY_DIR}/betterlinuxcnc-launch" DESTINATION ${CMAKE_INSTALL_BINDIR})
install(DIRECTORY src/ DESTINATION ${CMAKE_INSTALL_LIBDIR}/betterlinuxcnc/python
    PATTERN "__pycache__" EXCLUDE PATTERN "*.pyc" EXCLUDE PATTERN "*.egg-info" EXCLUDE)
install(FILES "${CMAKE_CURRENT_BINARY_DIR}/betterlinuxcnc-launcher.service"
    DESTINATION "${CMAKE_INSTALL_PREFIX}/lib/systemd/user")
install(FILES "${CMAKE_CURRENT_BINARY_DIR}/betterlinuxcnc-autostart.desktop"
    DESTINATION "/etc/xdg/autostart")
install(FILES "${CMAKE_CURRENT_SOURCE_DIR}/../../launcher.example.json"
    DESTINATION "${CMAKE_INSTALL_DATADIR}/doc/betterlinuxcnc/examples")
install(FILES packaging/betterlinuxcnc.desktop DESTINATION ${CMAKE_INSTALL_DATADIR}/applications)
install(FILES "${CMAKE_CURRENT_BINARY_DIR}/betterlinuxcnc-kiosk.desktop"
    DESTINATION "${CMAKE_INSTALL_DATADIR}/xsessions")
