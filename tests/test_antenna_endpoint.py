"""Exercise the firmware's actual antenna callbacks without radio hardware."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "firmware/main/app_main.cpp"


class AntennaEndpointTests(unittest.TestCase):
    def test_endpoint_is_appended_and_keeps_legacy_control(self):
        source = APP.read_text()
        self.assertLess(source.index("endpoint::electrical_meter::create("),
                        source.index("endpoint::on_off_plug_in_unit::create("))
        self.assertIn("external_antenna_config.on_off.on_off = g_external_antenna", source)
        self.assertIn("on_off_lighting.start_up_on_off = nullable<uint8_t>()", source)
        self.assertIn('CharSpan::fromCharString("External Antenna")', source)
        self.assertIn("label_provider.SetFixedLabels", source)
        self.assertIn("g_antenna_endpoint_id = endpoint::get_id(antenna_endpoint)", source)
        self.assertIn("meter_endpoint, &antenna_config, CLUSTER_FLAG_SERVER", source)
        self.assertIn("initialize_antenna_controls, 0", source)

    def test_firmware_version_metadata_is_consistent(self):
        identity = (ROOT / "firmware/main/MatterProjConfig.h").read_text()
        version = re.search(r'DEVICE_SOFTWARE_VERSION_STRING "([^"]+)"', identity)[1]
        number = re.search(r'DEVICE_SOFTWARE_VERSION (\d+)', identity)[1]
        self.assertIn(f'set(PROJECT_VER "{version}")', (ROOT / "firmware/CMakeLists.txt").read_text())
        self.assertIn(f'set(PROJECT_VER_NUMBER {number})', (ROOT / "firmware/CMakeLists.txt").read_text())
        self.assertIn(f'CONFIG_DEVICE_SOFTWARE_VERSION_NUMBER={number}\n',
                      (ROOT / "firmware/sdkconfig.defaults").read_text())

    @unittest.skipUnless(shutil.which("c++"), "A C++ compiler is needed for callback tests")
    def test_real_callbacks_sync_endpoints_and_preserve_saved_antenna(self):
        source = APP.read_text()
        callbacks = source[source.index("void publish_antenna_diagnostic(intptr_t)"):
                           source.index("esp_err_t identification_cb(")]
        harness = r'''
#include <cassert>
#include <cstdint>
#include <vector>
#include <utility>
#include <initializer_list>
using esp_err_t = int;
using gpio_num_t = int;
using CHIP_ERROR = int;
constexpr int ESP_OK = 0, ESP_ERR_INVALID_ARG = 22, CHIP_NO_ERROR = 0;
constexpr int CONFIG_SMARTMETER_RF_SWITCH_SELECT_GPIO = 14;
constexpr uint16_t kInvalidEndpointId = 0xffff;
constexpr uint32_t kSmartMeterDiagnosticsClusterId = 0xfff1fc01;
constexpr uint32_t kSmartMeterExternalAntennaAttributeId = 3;
#define ESP_LOGE(...) ((void)0)
#define ESP_LOGW(...) ((void)0)
struct esp_matter_attr_val_t { struct { bool b; } val; };
esp_matter_attr_val_t esp_matter_bool(bool value) { return {{value}}; }
esp_matter_attr_val_t esp_matter_invalid(void *) { return {{false}}; }
namespace OnOff { constexpr int Id = 6; namespace Attributes { namespace OnOff { constexpr int Id = 0; } } }
struct attribute_t { uint16_t endpoint; bool value; };
attribute_t attributes[] = {{1, false}, {2, false}};
uint16_t g_meter_endpoint_id = 1, g_antenna_endpoint_id = 2;
bool g_external_antenna = false, g_antenna_controls_ready = true;
bool saved = false, gpio_external = false, diagnostic = false;
bool fail_save = false, fail_gpio = false;
int saves = 0, gpio_writes = 0;
std::vector<std::pair<void (*)(intptr_t), intptr_t>> pending;
namespace attribute {
enum callback_type_t { PRE_UPDATE, POST_UPDATE };
attribute_t *get(uint16_t endpoint, uint32_t cluster, uint32_t id) {
    if (cluster != 6 || id != 0) return nullptr;
    for (auto &a : attributes) if (a.endpoint == endpoint) return &a;
    return nullptr;
}
int get_val(attribute_t *a, esp_matter_attr_val_t *value) { value->val.b = a->value; return ESP_OK; }
int update(uint16_t, uint32_t, uint32_t, esp_matter_attr_val_t *);
}
int attribute_update_cb(attribute::callback_type_t, uint16_t, uint32_t, uint32_t, esp_matter_attr_val_t *, void *);
namespace attribute {
int update(uint16_t endpoint, uint32_t cluster, uint32_t id, esp_matter_attr_val_t *value) {
    if (cluster == kSmartMeterDiagnosticsClusterId) { diagnostic = value->val.b; return ESP_OK; }
    auto *a = get(endpoint, cluster, id);
    assert(a);
    int result = attribute_update_cb(PRE_UPDATE, endpoint, cluster, id, value, nullptr);
    if (result == ESP_OK) a->value = value->val.b;
    return result;
}
}
int board_config_set_antenna(bool external) { ++saves; if (fail_save) return 88; saved = external; return ESP_OK; }
int gpio_set_level(gpio_num_t pin, int value) { assert(pin == 14); ++gpio_writes; if (fail_gpio) return 99; gpio_external = value; return ESP_OK; }
namespace DeviceLayer {
struct Manager { int ScheduleWork(void (*fn)(intptr_t), intptr_t arg) { pending.push_back({fn, arg}); return CHIP_NO_ERROR; } };
Manager &PlatformMgr() { static Manager manager; return manager; }
}
// Firmware code is inserted verbatim here, not reimplemented in this test.
__CALLBACKS__
void flush() {
    int count = 0;
    while (!pending.empty()) {
        assert(++count < 8); // Detect callback/update scheduling loops.
        auto work = pending.front(); pending.erase(pending.begin()); work.first(work.second);
    }
}
void reset(bool external = false) {
    g_external_antenna = saved = gpio_external = diagnostic = external;
    g_antenna_controls_ready = true; fail_save = fail_gpio = false;
    saves = gpio_writes = 0; pending.clear();
    for (auto &a : attributes) a.value = external;
}
int send(uint16_t endpoint, bool external) {
    auto value = esp_matter_bool(external);
    return attribute::update(endpoint, 6, 0, &value);
}
int main() {
    reset();
    // New Apple endpoint On, legacy HA endpoint Off, and repeated toggles.
    for (auto request : {std::pair<uint16_t, bool>{2, true}, {1, false}, {1, true}, {2, false}}) {
        const int previous_saves = saves;
        assert(send(request.first, request.second) == ESP_OK);
        flush();
        assert(g_external_antenna == request.second && saved == request.second);
        assert(gpio_external == request.second && diagnostic == request.second);
        assert(attributes[0].value == request.second && attributes[1].value == request.second);
        assert(saves == previous_saves + 1); // Mirrored writes never persist again.
    }
    // Same-value, unrelated endpoint/cluster/attribute, POST and null input.
    reset(); auto value = esp_matter_bool(true);
    assert(send(2, false) == ESP_OK && saves == 0 && pending.empty());
    assert(attribute_update_cb(attribute::PRE_UPDATE, 3, 6, 0, &value, nullptr) == ESP_OK);
    assert(attribute_update_cb(attribute::PRE_UPDATE, 2, 7, 0, &value, nullptr) == ESP_OK);
    assert(attribute_update_cb(attribute::PRE_UPDATE, 2, 6, 1, &value, nullptr) == ESP_OK);
    assert(attribute_update_cb(attribute::POST_UPDATE, 2, 6, 0, &value, nullptr) == ESP_OK);
    assert(attribute_update_cb(attribute::PRE_UPDATE, 2, 6, 0, nullptr, nullptr) == ESP_ERR_INVALID_ARG);
    assert(saves == 0 && gpio_writes == 0 && !g_external_antenna);
    // Failed persistence rejects the command before changing RF or attributes.
    fail_save = true;
    assert(send(2, true) == 88);
    assert(!saved && !gpio_external && !attributes[1].value && pending.empty());
    // Failed GPIO restores the previous saved selection and rejects the command.
    reset(); fail_gpio = true;
    assert(send(1, true) == 99);
    assert(!saved && !g_external_antenna && !attributes[0].value && saves == 2 && pending.empty());
    // Startup and BOOT/USB recovery: stale Matter Off must not overwrite a
    // saved external antenna; sync both attributes before enabling commands.
    reset(true); g_antenna_controls_ready = false;
    attributes[0].value = attributes[1].value = false;
    assert(send(2, false) == ESP_OK && saved && g_external_antenna && saves == 0);
    initialize_antenna_controls(0); flush();
    assert(g_antenna_controls_ready && attributes[0].value && attributes[1].value && diagnostic);
    assert(saves == 0 && gpio_writes == 0);
    assert(send(2, false) == ESP_OK); flush();
    assert(!saved && !g_external_antenna && !attributes[0].value && !attributes[1].value);
}
'''.replace("__CALLBACKS__", callbacks)
        with tempfile.TemporaryDirectory() as directory:
            test = Path(directory) / "antenna.cpp"
            executable = Path(directory) / "antenna-test"
            test.write_text(harness)
            result = subprocess.run([shutil.which("c++"), "-std=c++17", "-Wall", "-Wextra",
                                     str(test), "-o", str(executable)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            subprocess.run([str(executable)], check=True)


if __name__ == "__main__":
    unittest.main()
