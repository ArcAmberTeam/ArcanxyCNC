cmake_minimum_required(VERSION 3.22)
project(BetterLinuxCNC VERSION 26.11.21.2 LANGUAGES CXX)

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
option(BETTERCNC_REUSE_INSTALLED_HOMING "Reuse the installed HOMEMOD for same-version maintenance application builds" OFF)
if(BETTERCNC_BUILD_MESA_HOMING AND BETTERCNC_REUSE_INSTALLED_HOMING)
    message(FATAL_ERROR "Choose either a new homing build or the installed module")
endif()
if(BETTERCNC_BUILD_MESA_HOMING AND NOT BETTERCNC_BUILD_SYSTEM_SERVICES)
    message(FATAL_ERROR "The native homing release requires the complete application services")
endif()

add_subdirectory(app/controller)
install(DIRECTORY app/platform/error-records/python/src/bettercnc_error_records
    DESTINATION "${CMAKE_INSTALL_LIBDIR}/betterlinuxcnc/python"
    PATTERN "__pycache__" EXCLUDE PATTERN "*.pyc" EXCLUDE)
add_subdirectory(app/launcher)
if(BETTERCNC_BUILD_SYSTEM_SERVICES)
    add_subdirectory(app/platform/cam-link)
    add_subdirectory(app/platform/updater)
    add_subdirectory(app/platform/mesa-update)
    add_subdirectory(app/platform/configuration)
    add_subdirectory(app/platform/package-build)
    add_subdirectory(app/platform/local-update)
    add_subdirectory(app/platform/error-records)
    add_subdirectory(app/platform/system-info)
endif()
add_subdirectory(app/desktop)
add_subdirectory(tools/appliance)
if(BETTERCNC_BUILD_MESA_HOMING)
    add_subdirectory(tools/mesa-homing)
endif()

if(BETTERCNC_REUSE_INSTALLED_HOMING)
    install(FILES "/usr/lib/linuxcnc/modules/zhulong_homing.so"
        DESTINATION "${CMAKE_INSTALL_LIBDIR}/linuxcnc/modules")
    install(FILES "/usr/share/betterlinuxcnc/homing/provenance.json"
        DESTINATION "${CMAKE_INSTALL_DATADIR}/betterlinuxcnc/homing")
endif()

set(BETTERCNC_LOCAL_PACKAGE_VERSION "" CACHE STRING "Installed base version retained by maintenance builds")
if(BETTERCNC_LOCAL_PACKAGE_VERSION)
    if(NOT BETTERCNC_REUSE_INSTALLED_HOMING OR NOT BETTERCNC_LOCAL_PACKAGE_VERSION MATCHES "^[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+$")
        message(FATAL_ERROR "A local package version requires installed homing and a four-part application version")
    endif()
    file(READ "${CMAKE_CURRENT_SOURCE_DIR}/app/desktop/python/bettercnc/__init__.py" local_metadata)
    string(REGEX REPLACE "__version__ = \"[^\"]+\"" "__version__ = \"${BETTERCNC_LOCAL_PACKAGE_VERSION}\"" local_metadata "${local_metadata}")
    file(MAKE_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/local-version")
    file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/local-version/__init__.py" "${local_metadata}")
    install(FILES "${CMAKE_CURRENT_BINARY_DIR}/local-version/__init__.py"
        DESTINATION "${CMAKE_INSTALL_LIBDIR}/betterlinuxcnc/python/bettercnc")
endif()

set(CPACK_PACKAGE_NAME "betterlinuxcnc")
# Application releases have their own version; VERSION tracks the native core.
set(CPACK_PACKAGE_VERSION "${PROJECT_VERSION}")
if(BETTERCNC_LOCAL_PACKAGE_VERSION)
    set(CPACK_PACKAGE_VERSION "${BETTERCNC_LOCAL_PACKAGE_VERSION}")
endif()
set(CPACK_DEBIAN_PACKAGE_CONFLICTS "betterlinuxcnc-qt")
set(CPACK_DEBIAN_PACKAGE_REPLACES "betterlinuxcnc-qt")
set(CPACK_DEBIAN_PACKAGE_PROVIDES "betterlinuxcnc-qt (= ${CPACK_PACKAGE_VERSION})")
set(CPACK_DEBIAN_FILE_NAME "DEB-DEFAULT")
set(CPACK_SET_DESTDIR ON)
set(CPACK_PACKAGING_INSTALL_PREFIX "/usr")
set(CPACK_DEBIAN_PACKAGE_CONTROL_STRICT_PERMISSION ON)
list(APPEND CPACK_DEBIAN_PACKAGE_CONTROL_EXTRA
    "${CMAKE_CURRENT_SOURCE_DIR}/tools/appliance/packaging/postinst")
set(CPACK_PACKAGE_CONTACT "BetterLinuxCNC maintainers")
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "Controller services and headless tools for LinuxCNC")
if(NOT BETTERCNC_BUILD_SYSTEM_SERVICES)
    set(CPACK_DEBIAN_PACKAGE_ARCHITECTURE "all")
endif()
set(CPACK_DEBIAN_PACKAGE_DEPENDS "python3 (>= 3.11), linuxcnc-uspace (>= 2.9), dbus-user-session, lightdm, xserver-xorg, x11-xserver-utils, openssh-server, sudo, passwd, procps, pci.ids")
if(BETTERCNC_BUILD_SYSTEM_SERVICES)
    string(APPEND CPACK_DEBIAN_PACKAGE_DEPENDS ", libgtk-3-0t64, libnss3, libasound2t64, libgbm1, libnotify4, libxss1, libxtst6, libdrm2, libxkbcommon0, libx11-xcb1")
    string(APPEND CPACK_DEBIAN_PACKAGE_DEPENDS ", pamtester, polkitd, systemd, util-linux, ca-certificates, apt, dpkg, mesaflash, git, cmake, build-essential, pkg-config, rustup, libaio1t64, libmecab2, libnuma1, libtirpc3t64, libssl3t64, libstdc++6 (>= 14)")
    file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/conffiles" "/etc/betterlinuxcnc/updater.json\n")
    list(APPEND CPACK_DEBIAN_PACKAGE_CONTROL_EXTRA "${CMAKE_CURRENT_BINARY_DIR}/conffiles")
endif()
include(CPack)
