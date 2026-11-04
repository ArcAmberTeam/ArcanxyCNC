cmake_minimum_required(VERSION 3.22)
project(BetterLinuxCNC VERSION 26.11.04.6 LANGUAGES CXX)

# Application composition only; the native LinuxCNC core is built from src/Makefile.
include(cmake/ApplicationInstall.cmake)
if(NOT CMAKE_INSTALL_PREFIX STREQUAL "/usr"
    OR NOT CMAKE_INSTALL_BINDIR STREQUAL "bin"
    OR NOT CMAKE_INSTALL_SBINDIR STREQUAL "sbin"
    OR NOT CMAKE_INSTALL_LIBDIR STREQUAL "lib"
    OR NOT CMAKE_INSTALL_DATADIR STREQUAL "share"
    OR NOT CMAKE_INSTALL_FULL_LIBDIR STREQUAL "/usr/lib")
    message(FATAL_ERROR "The complete application requires /usr with bin, sbin, lib and share destinations. Use a fresh build directory if an earlier cache contains absolute install paths.")
endif()
include(CTest)
set(BETTERCNC_PROJECT_DIR "/etc/betterlinuxcnc" CACHE PATH "Runtime project directory containing launcher.json")
option(BETTERCNC_BUILD_SYSTEM_SERVICES "Build and install Rust system services" ON)
option(BETTERCNC_BUILD_MESA_HOMING "Build the pinned homing module against this native source revision (GitHub CI only)" OFF)
if(BETTERCNC_BUILD_MESA_HOMING AND NOT BETTERCNC_BUILD_SYSTEM_SERVICES)
    message(FATAL_ERROR "The native homing release requires the complete application services")
endif()

add_subdirectory(app/controller)
add_subdirectory(app/launcher)
if(BETTERCNC_BUILD_SYSTEM_SERVICES)
    add_subdirectory(app/platform/cam-link)
    add_subdirectory(app/platform/updater)
    add_subdirectory(app/platform/mesa-update)
    add_subdirectory(app/platform/manage-ini)
    add_subdirectory(app/platform/account-management/cnc-maint)
endif()
add_subdirectory(app/desktop)
add_subdirectory(tools/appliance)
if(BETTERCNC_BUILD_MESA_HOMING)
    add_subdirectory(tools/mesa-homing)
endif()

set(CPACK_PACKAGE_NAME "betterlinuxcnc-qt")
# Application releases have their own version; VERSION tracks the native core.
set(CPACK_PACKAGE_VERSION "${PROJECT_VERSION}")
set(CPACK_DEBIAN_FILE_NAME "DEB-DEFAULT")
set(CPACK_SET_DESTDIR ON)
set(CPACK_PACKAGING_INSTALL_PREFIX "/usr")
set(CPACK_DEBIAN_PACKAGE_CONTROL_STRICT_PERMISSION ON)
list(APPEND CPACK_DEBIAN_PACKAGE_CONTROL_EXTRA
    "${CMAKE_CURRENT_SOURCE_DIR}/tools/appliance/packaging/postinst")
set(CPACK_PACKAGE_CONTACT "BetterLinuxCNC maintainers")
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "Native PySide6/QML desktop for LinuxCNC")
if(NOT BETTERCNC_BUILD_SYSTEM_SERVICES)
    set(CPACK_DEBIAN_PACKAGE_ARCHITECTURE "all")
endif()
set(CPACK_DEBIAN_PACKAGE_DEPENDS "python3 (>= 3.11), python3-pyside6.qtcore (>= 6.8), python3-pyside6.qtgui, python3-pyside6.qtqml, python3-pyside6.qtquick, python3-pyside6.qtquickcontrols2, linuxcnc-uspace (>= 2.9), python3-opengl, qml6-module-qtqml, qml6-module-qtqml-models, qml6-module-qtquick, qml6-module-qtquick-window, qml6-module-qtquick-controls, qml6-module-qtquick-layouts, qml6-module-qtquick-templates, qml6-module-qtquick-shapes, qml6-module-qtquick-dialogs, qml6-module-qtqml-workerscript, fonts-noto-cjk, fonts-liberation, dbus-user-session, lightdm, xserver-xorg, x11-xserver-utils, openssh-server, sudo, passwd, procps")
if(BETTERCNC_BUILD_SYSTEM_SERVICES)
    string(APPEND CPACK_DEBIAN_PACKAGE_DEPENDS ", polkitd, systemd, util-linux, ca-certificates, apt, dpkg, mesaflash")
    file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/conffiles" "/etc/betterlinuxcnc/updater.json\n")
    list(APPEND CPACK_DEBIAN_PACKAGE_CONTROL_EXTRA "${CMAKE_CURRENT_BINARY_DIR}/conffiles")
endif()
include(CPack)
