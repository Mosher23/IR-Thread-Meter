"""Run the firmware's BOOT gesture state machine and saved-toggle action."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BootButtonTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("c++"), "A C++ compiler is required")
    def test_hold_taps_reset_debounce_wrap_and_persistence_failure(self):
        source = (ROOT / "firmware/main/app_main.cpp").read_text()
        action = source[source.index("void toggle_antenna_and_restart("):
                        source.index("void factory_reset_button_task(")]
        harness = r'''
#include "boot_button.h"
#include <cassert>
#include <cstdint>
#include <initializer_list>
using A = BootButtonGestures::Action;
constexpr int ESP_OK = 0;
using esp_err_t = int;
bool g_external_antenna = false, saved = false, fail_save = false;
int writes = 0, restarts = 0;
#define ESP_LOGW(...) ((void)reason)
#define ESP_LOGE(...) ((void)0)
int board_config_set_antenna(bool value) {
    ++writes;
    if (fail_save) return 77;
    saved = value;
    return ESP_OK;
}
void esp_restart() { ++restarts; }
__ACTION__
A hold(uint32_t duration, uint32_t start = 0) {
    BootButtonGestures b;
    assert(b.Update(true, start) == A::None);
    return b.Update(false, start + duration);
}
int main() {
    // The requested hold acts on release, once, without a reset at five seconds.
    assert(hold(2999) == A::None);
    assert(hold(3000) == A::ToggleAntenna);
    assert(hold(5000) == A::ToggleAntenna);
    assert(hold(9999) == A::ToggleAntenna);
    BootButtonGestures b;
    assert(b.Update(true, 0) == A::None);
    assert(b.Update(true, 3000) == A::None);
    assert(b.Update(true, 5000) == A::None);
    assert(b.Update(false, 5001) == A::ToggleAntenna);
    assert(b.Update(false, 5100) == A::None);
    // A reset hold never toggles first, repeats while held, or toggles on release.
    b = {};
    assert(b.Update(true, 0) == A::None);
    assert(b.Update(true, 9999) == A::None);
    assert(b.Update(true, 10000) == A::FactoryReset);
    assert(b.Update(true, 15000) == A::None);
    assert(b.Update(false, 15001) == A::None);
    assert(hold(10000) == A::FactoryReset); // Even if a polling tick is missed.
    // Triple-tap recovery is preserved; contact bounce does not count as taps.
    b = {};
    for (uint32_t t : {0u, 40u, 80u}) {
        assert(b.Update(true, t) == A::None);
        assert(b.Update(false, t + 10) == A::None);
    }
    for (uint32_t t : {200u, 400u}) {
        assert(b.Update(true, t) == A::None);
        assert(b.Update(false, t + 100) == A::None);
    }
    assert(b.Update(true, 600) == A::None);
    assert(b.Update(false, 700) == A::ToggleAntenna);
    // Expired or interrupted tap sequences cannot produce an unexpected toggle.
    b = {};
    assert(b.Update(true, 0) == A::None);
    assert(b.Update(false, 100) == A::None);
    assert(b.Update(false, 2101) == A::None);
    assert(b.Update(true, 2200) == A::None);
    assert(b.Update(false, 2300) == A::None);
    assert(b.Update(true, 2400) == A::None);
    assert(b.Update(false, 3400) == A::None); // Medium hold clears the sequence.
    assert(b.Update(true, 3500) == A::None);
    assert(b.Update(false, 3600) == A::None);
    assert(hold(3000, UINT32_MAX - 1000) == A::ToggleAntenna);
    assert(hold(10000, UINT32_MAX - 1000) == A::FactoryReset);
    // The real action persists the opposite antenna before rebooting.
    toggle_antenna_and_restart("test");
    assert(saved && writes == 1 && restarts == 1);
    g_external_antenna = true;
    toggle_antenna_and_restart("test");
    assert(!saved && writes == 2 && restarts == 2);
    fail_save = true;
    toggle_antenna_and_restart("test");
    assert(!saved && writes == 3 && restarts == 2);
}
'''.replace("__ACTION__", action)
        with tempfile.TemporaryDirectory() as directory:
            cpp = Path(directory) / "boot.cpp"
            binary = Path(directory) / "boot-test"
            cpp.write_text(harness)
            result = subprocess.run([shutil.which("c++"), "-std=c++17", "-Wall", "-Wextra",
                                     "-I", str(ROOT / "firmware/main"), str(cpp), "-o", str(binary)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    unittest.main()
