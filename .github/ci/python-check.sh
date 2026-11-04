#!/bin/bash
# Public CI scopes for the installed Python packages; vendor seams stay in tests.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
scope=${1:?Usage: python-check.sh service|preview|desktop|launcher}
python_bin=${PYTHON:-python3}
case "$scope" in
  launcher)
    package=app/launcher
    paths=(app/launcher/src app/launcher/tests)
    tests=(test_launcher.py test_kiosk_session.py test_installation.py)
    test_dir=app/launcher/tests
    ;;
  service)
    package=app/controller
    paths=(app/controller/src/betterlinuxcnc_service app/controller/src/bettercnc_controller
           app/controller/tests/test_service.py app/controller/tests/test_control_service.py app/controller/tests/test_controller.py
           app/controller/tests/test_received_jobs.py app/controller/tests/test_homing_policy.py app/controller/tests/test_cam_homing.py
           app/controller/tests/test_machine_configuration.py)
    tests=(test_service.py test_control_service.py test_controller.py test_received_jobs.py test_homing_policy.py test_cam_homing.py test_machine_configuration.py)
    test_dir=app/controller/tests
    ;;
  preview)
    package=app/controller
    paths=(app/controller/src/bettercnc_preview app/controller/tests/test_preview.py)
    tests=(test_preview.py)
    test_dir=app/controller/tests
    # Missing native extensions must fail here, never silently skip real RS274 tests.
    "$python_bin" -c 'import gcode, linuxcnc; print(gcode.__file__, linuxcnc.__file__)'
    ;;
  desktop)
    package=app/desktop
    paths=(app/desktop/python app/desktop/tests/python app/desktop/scripts app/desktop/app/main.py app/desktop/setup.py)
    tests=('test_*.py')
    test_dir=app/desktop/tests/python
    export QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software QT_QUICK_CONTROLS_STYLE=Basic
    ;;
  *) echo "Unknown Python CI scope: $scope" >&2; exit 2 ;;
esac
"$python_bin" -m ruff check "${paths[@]}" app/platform/error-records/python app/platform/error-records/runtime
"$python_bin" -m ruff format --check "${paths[@]}" app/platform/error-records/python app/platform/error-records/runtime
"$python_bin" app/desktop/scripts/check_boundaries.py
package_dist=$(mktemp -d)
trap 'rm -rf "$package_dist"' EXIT
"$python_bin" -m build --no-isolation --outdir "$package_dist" app/platform/error-records/python
"$python_bin" -m build --no-isolation --outdir "$package_dist" "$package"
"$python_bin" -m pip install --no-deps --force-reinstall "$package_dist"/*.whl
for test_file in "${tests[@]}"; do
  env -u PYTHONPATH "$python_bin" -m unittest discover -s "$test_dir" -p "$test_file" -v
done
mkdir -p "$package/dist"
cp "$package_dist"/* "$package/dist/"
