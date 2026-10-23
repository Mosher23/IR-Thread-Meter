"""Exercise the actual LED task and blocking antenna confirmation without hardware."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class StatusLedTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('c++'), 'A C++ compiler is required')
    def test_confirmation_overrides_receive_and_finishes_before_return(self):
        source = (ROOT / 'firmware/main/smart_meter.cpp').read_text()
        constants = source[source.index('constexpr ledc_mode_t kLedSpeedMode'):
                           source.index('struct PublishSnapshot')]
        task = source[source.index('void set_led_duty('):source.index('esp_err_t start_status_led(')]
        api = source[source.index('esp_err_t smart_meter_confirm_antenna_toggle('):
                     source.index('esp_err_t smart_meter_start(')]
        harness = r'''
#include <atomic>
#include <cassert>
#include <cstdint>
#include <vector>
using TickType_t = uint32_t;
using esp_err_t = int;
using ledc_mode_t = int;
using ledc_timer_t = int;
using ledc_channel_t = int;
constexpr int ESP_OK = 0, ESP_ERR_INVALID_STATE = 1, ESP_ERR_TIMEOUT = 2;
constexpr int LEDC_LOW_SPEED_MODE = 0, LEDC_TIMER_0 = 0, LEDC_CHANNEL_0 = 0;
constexpr int LEDC_TIMER_10_BIT = 10, pdTRUE = 1;
#define pdMS_TO_TICKS(ms) (ms)
__CONSTANTS__
void *g_led_task_handle = reinterpret_cast<void *>(1);
std::atomic_bool g_antenna_confirmation_pending{false};
TickType_t now = 0;
std::vector<uint32_t> duties, delays;
bool in_led = false, run_led = true;
unsigned notifications = 0, takes = 0;
struct EndIteration {};
TickType_t xTaskGetTickCount() { return now; }
int ledc_set_duty(int, int, uint32_t duty) { duties.push_back(duty); return ESP_OK; }
int ledc_update_duty(int, int) { return ESP_OK; }
void xTaskNotifyGive(void *) { ++notifications; }
uint32_t ulTaskNotifyTake(int, TickType_t) {
    if (++takes > 1) throw EndIteration{};
    auto result = notifications; notifications = 0; return result;
}
void vTaskDelay(TickType_t duration);
__TASK__
void run_iteration() {
    takes = 0; in_led = true;
    try { status_led_task(nullptr); } catch (EndIteration &) {}
    in_led = false;
}
void vTaskDelay(TickType_t duration) {
    now += duration;
    if (in_led) {
        delays.push_back(duration);
        // Simulate incoming SML notifications throughout the confirmation.
        xTaskNotifyGive(g_led_task_handle);
    } else if (run_led) {
        run_iteration();
    }
}
__API__
int main() {
    assert(smart_meter_confirm_antenna_toggle() == ESP_OK);
    assert(!g_antenna_confirmation_pending.load());
    assert(duties == std::vector<uint32_t>({1023, 0, 1023, 0, 1023, 0}));
    assert(delays == std::vector<uint32_t>({80, 80, 80, 80, 80, 80}));
    assert(now >= 480 && now < 1000);
    // Normal receive pulses still work after the exclusive pattern.
    duties.clear(); run_iteration();
    assert(duties == std::vector<uint32_t>({1023}));
    // The API fails safely if unavailable and never hangs on a stopped task.
    g_led_task_handle = nullptr;
    assert(smart_meter_confirm_antenna_toggle() == ESP_ERR_INVALID_STATE);
    g_led_task_handle = reinterpret_cast<void *>(1);
    run_led = false; now = UINT32_MAX - 100;
    const auto started = now;
    assert(smart_meter_confirm_antenna_toggle() == ESP_ERR_TIMEOUT);
    assert(now - started == 1000); // Also handles tick counter wrap.
}
'''.replace('__CONSTANTS__', constants).replace('__TASK__', task).replace('__API__', api)
        with tempfile.TemporaryDirectory() as directory:
            cpp = Path(directory) / 'led.cpp'
            binary = Path(directory) / 'led-test'
            cpp.write_text(harness)
            result = subprocess.run([shutil.which('c++'), '-std=c++17', '-Wall', '-Wextra',
                                     str(cpp), '-o', str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            subprocess.run([str(binary)], check=True)
