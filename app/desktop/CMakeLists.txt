cmake_minimum_required(VERSION 3.22)

# Standalone builds own the desktop only. The repository root assembles the product.
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
    project(BetterLinuxCNCDesktop VERSION 26.10.26.1 LANGUAGES CXX)
    include("${CMAKE_CURRENT_SOURCE_DIR}/../../cmake/ApplicationInstall.cmake")
    message(STATUS "Building the desktop only; configure the repository root for the complete application")
endif()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
find_package(Python3 3.11 REQUIRED COMPONENTS Interpreter)
configure_file(app/betterlinuxcnc.in betterlinuxcnc @ONLY)

include(CTest)
if(BUILD_TESTING)
    find_package(Qt6 6.8 REQUIRED COMPONENTS Quick QuickControls2 QuickTest)
    qt_standard_project_setup(REQUIRES 6.8)
    qt_add_executable(qml-ui-tests tests/main.cpp)
    target_link_libraries(qml-ui-tests PRIVATE Qt6::QuickTest Qt6::QuickControls2)
    target_compile_definitions(qml-ui-tests PRIVATE
        QUICK_TEST_SOURCE_DIR="${CMAKE_CURRENT_SOURCE_DIR}/tests")
    add_test(NAME qml-ui COMMAND qml-ui-tests -import "${CMAKE_CURRENT_SOURCE_DIR}/qml")
    set_tests_properties(qml-ui PROPERTIES ENVIRONMENT
        "QT_QPA_PLATFORM=offscreen;QT_QUICK_BACKEND=software;QT_QUICK_CONTROLS_STYLE=Basic")
    add_test(NAME module-boundaries COMMAND Python3::Interpreter
        "${CMAKE_CURRENT_SOURCE_DIR}/scripts/check_boundaries.py")
    file(GLOB_RECURSE QML_SOURCES CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/qml/*.qml")
    list(APPEND QML_SOURCES "${CMAKE_CURRENT_SOURCE_DIR}/tests/VisualPreview.qml")
    add_test(NAME qml-lint COMMAND Qt6::qmllint --max-warnings 0
        -I "${CMAKE_CURRENT_SOURCE_DIR}/qml" ${QML_SOURCES})
    add_test(NAME python-integration COMMAND Python3::Interpreter -m unittest discover
        -s "${CMAKE_CURRENT_SOURCE_DIR}/tests/python" -v)
    set_tests_properties(python-integration PROPERTIES ENVIRONMENT
        "PYTHONPATH=${CMAKE_CURRENT_SOURCE_DIR}/python;QT_QPA_PLATFORM=offscreen;QT_QUICK_BACKEND=software;QT_QUICK_CONTROLS_STYLE=Basic")
    add_test(NAME desktop-startup COMMAND Python3::Interpreter
        "${CMAKE_CURRENT_SOURCE_DIR}/app/main.py" --smoke-test
        --socket "${CMAKE_CURRENT_BINARY_DIR}/no-controller-for-startup.sock")
    set_tests_properties(desktop-startup PROPERTIES ENVIRONMENT
        "QT_QPA_PLATFORM=offscreen;QT_QUICK_BACKEND=software;QT_QUICK_CONTROLS_STYLE=Basic"
        FAIL_REGULAR_EXPRESSION "QQmlApplicationEngine failed;ReferenceError:;TypeError:;Unable to assign;Binding loop detected")
    add_test(NAME interactive-gui-startup COMMAND Python3::Interpreter
        "${CMAKE_CURRENT_SOURCE_DIR}/tests/interactive/main.py" --smoke-test)
    set_tests_properties(interactive-gui-startup PROPERTIES ENVIRONMENT
        "QT_QPA_PLATFORM=offscreen;QT_QUICK_BACKEND=software;QT_QUICK_CONTROLS_STYLE=Basic"
        FAIL_REGULAR_EXPRESSION "QQmlApplicationEngine failed;ReferenceError:;TypeError:;Unable to assign;Binding loop detected")
    add_test(NAME external-interface-integration COMMAND Python3::Interpreter
        "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_simulation.py" -v)
    set_tests_properties(external-interface-integration PROPERTIES ENVIRONMENT
        "QT_QPA_PLATFORM=offscreen;QT_QUICK_BACKEND=software;QT_QUICK_CONTROLS_STYLE=Basic")
    add_test(NAME interactive-gui-lint COMMAND Qt6::qmllint --max-warnings 0
        -I "${CMAKE_CURRENT_SOURCE_DIR}/qml"
        "${CMAKE_CURRENT_SOURCE_DIR}/tests/interactive/Interactive.qml"
        "${CMAKE_CURRENT_SOURCE_DIR}/tests/interactive/InteractiveBackend.qml")
    add_test(NAME visual-preview-startup COMMAND Python3::Interpreter
        "${CMAKE_CURRENT_SOURCE_DIR}/tests/visual_preview.py"
        --capture "${CMAKE_CURRENT_BINARY_DIR}/visual-preview.png")
    set_tests_properties(visual-preview-startup PROPERTIES ENVIRONMENT
        "QT_QPA_PLATFORM=offscreen;QT_QUICK_BACKEND=software;QT_QUICK_CONTROLS_STYLE=Basic"
        FAIL_REGULAR_EXPRESSION "QQmlApplicationEngine failed;ReferenceError:;TypeError:;Unable to assign;Binding loop detected")
    add_test(NAME guided-preview-startup COMMAND Python3::Interpreter
        "${CMAKE_CURRENT_SOURCE_DIR}/tests/visual_preview.py"
        --interface guided --stage preview --width 760 --height 640
        --capture "${CMAKE_CURRENT_BINARY_DIR}/guided-preview.png")
    set_tests_properties(guided-preview-startup PROPERTIES ENVIRONMENT
        "QT_QPA_PLATFORM=offscreen;QT_QUICK_BACKEND=software;QT_QUICK_CONTROLS_STYLE=Basic"
        FAIL_REGULAR_EXPRESSION "QQmlApplicationEngine failed;ReferenceError:;TypeError:;Unable to assign;Binding loop detected")
    set_property(TEST python-integration desktop-startup interactive-gui-startup
        external-interface-integration visual-preview-startup guided-preview-startup
        APPEND PROPERTY ENVIRONMENT_MODIFICATION
        "PYTHONPATH=path_list_prepend:${CMAKE_CURRENT_SOURCE_DIR}/../platform/error-records/python/src")
endif()

install(PROGRAMS "${CMAKE_CURRENT_BINARY_DIR}/betterlinuxcnc" DESTINATION ${CMAKE_INSTALL_BINDIR})
install(DIRECTORY python/bettercnc DESTINATION ${CMAKE_INSTALL_LIBDIR}/betterlinuxcnc/python
    PATTERN "__pycache__" EXCLUDE PATTERN "*.pyc" EXCLUDE)
install(DIRECTORY qml/ DESTINATION ${CMAKE_INSTALL_DATADIR}/betterlinuxcnc/qml)
install(FILES LICENSE DESTINATION ${CMAKE_INSTALL_DATADIR}/doc/betterlinuxcnc-qt RENAME COPYING)
install(FILES qml/BetterCnc/Catalog/assets/NOTICE.md
    qml/BetterCnc/Catalog/assets/TOOLBAR-LICENSE
    DESTINATION ${CMAKE_INSTALL_DATADIR}/doc/betterlinuxcnc-qt)
