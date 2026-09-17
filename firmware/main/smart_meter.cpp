#include "smart_meter.h"

#include "electrical_meter_delegate.h"
#include "sml.h"

#include <app/data-model/Nullable.h>
#include <data_model_provider/clusters/electrical_energy_measurement/integration.h>
#include <driver/gpio.h>
#include <driver/ledc.h>
#include <driver/uart.h>
#include <esp_check.h>
#include <esp_console.h>
#include <esp_log.h>
#include <esp_matter.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include <freertos/semphr.h>
#include <freertos/task.h>
#include <atomic>
#include <ctype.h>
#include <limits.h>
#include <new>
#include <platform/CHIPDeviceLayer.h>
#include <stdio.h>
#include <string.h>
#include <system/SystemClock.h>

using namespace chip;
using namespace chip::app;
using namespace chip::app::Clusters;

namespace {
constexpr char TAG[] = "smart_meter";

enum class ReadingType : uint8_t {
    ActivePower,
    ImportedEnergy,
    ExportedEnergy,
};

struct ObisHandler {
    uint8_t obis[6];
    sml_units_t unit;
    ReadingType type;
};

constexpr ObisHandler kHandlers[] = {
    {{0x01, 0x00, 0x10, 0x07, 0x00, 0xff}, SML_WATT, ReadingType::ActivePower},
    {{0x01, 0x00, 0x01, 0x08, 0x00, 0xff}, SML_WATT_HOUR, ReadingType::ImportedEnergy},
    {{0x01, 0x00, 0x02, 0x08, 0x00, 0xff}, SML_WATT_HOUR, ReadingType::ExportedEnergy},
};

constexpr uint8_t kMeterIdObis[] = {0x01, 0x00, 0x60, 0x01, 0x00, 0xff};
constexpr uint8_t kMeterManufacturerObis[] = {0x01, 0x00, 0x60, 0x32, 0x01, 0x01};
constexpr size_t kMaxMeterIdentityLength = kSmartMeterIdentityMaxLength;

struct TextReading {
    bool valid = false;
    char value[kMaxMeterIdentityLength + 1] = {};
};

struct Reading {
    bool valid = false;
    int64_t value = 0; // Matter units: mW or mWh
    int64_t last_published = 0;
    TickType_t last_publish_tick = 0;
};

struct CandidateReading {
    bool valid = false;
    int64_t value = 0;
};

struct PendingFrame {
    CandidateReading power;
    CandidateReading imported;
    CandidateReading exported;
    TextReading meter_id;
    TextReading manufacturer;
};

struct State {
    uint16_t endpoint_id = 0;
    SmartMeterPowerDelegate *power_delegate = nullptr;
    Reading power;
    Reading imported;
    Reading exported;
    TextReading meter_id;
    TextReading manufacturer;
    PendingFrame pending;
};

State g_state;

struct PinRequest {
    char digits[4];
};

QueueHandle_t g_pin_queue = nullptr;
SemaphoreHandle_t g_uart_mutex = nullptr;
TaskHandle_t g_led_task_handle = nullptr;
std::atomic_bool g_pin_busy{false};

constexpr ledc_mode_t kLedSpeedMode = LEDC_LOW_SPEED_MODE;
constexpr ledc_timer_t kLedTimer = LEDC_TIMER_0;
constexpr ledc_channel_t kLedChannel = LEDC_CHANNEL_0;
constexpr uint32_t kLedMaxDuty = (1U << LEDC_TIMER_10_BIT) - 1U;
constexpr uint32_t kLedBreathMinDuty = 4;
constexpr uint32_t kLedBreathMaxDuty = 180;
constexpr uint32_t kLedStepMs = 20;
constexpr uint32_t kLedBreathSteps = 200;
constexpr uint32_t kLedReceivePulseMs = 160;

struct PublishSnapshot {
    uint16_t endpoint_id;
    SmartMeterPowerDelegate *delegate;
    bool publish_power;
    bool power_valid;
    int64_t power;
    bool publish_imported;
    bool imported_valid;
    int64_t imported;
    bool publish_exported;
    bool exported_valid;
    int64_t exported;
};

struct IdentitySnapshot {
    uint16_t endpoint_id;
    bool meter_id_changed;
    bool manufacturer_changed;
    char meter_id[kMaxMeterIdentityLength + 1];
    char manufacturer[kMaxMeterIdentityLength + 1];
};

CandidateReading &pending_for(ReadingType type)
{
    switch (type) {
    case ReadingType::ActivePower:
        return g_state.pending.power;
    case ReadingType::ImportedEnergy:
        return g_state.pending.imported;
    case ReadingType::ExportedEnergy:
        return g_state.pending.exported;
    }
    return g_state.pending.power;
}

void commit_candidate(const CandidateReading &candidate, Reading &reading)
{
    if (candidate.valid) {
        reading.value = candidate.value;
        reading.valid = true;
    }
}

bool commit_text(const TextReading &candidate, TextReading &reading)
{
    if (!candidate.valid || (reading.valid && strcmp(candidate.value, reading.value) == 0)) {
        return false;
    }
    reading = candidate;
    return true;
}

uint8_t commit_pending_frame()
{
    commit_candidate(g_state.pending.power, g_state.power);
    commit_candidate(g_state.pending.imported, g_state.imported);
    commit_candidate(g_state.pending.exported, g_state.exported);
    const bool meter_id_changed = commit_text(g_state.pending.meter_id, g_state.meter_id);
    const bool manufacturer_changed = commit_text(g_state.pending.manufacturer, g_state.manufacturer);
    g_state.pending = {};
    return static_cast<uint8_t>((meter_id_changed ? 1 : 0) |
                                (manufacturer_changed ? 2 : 0));
}

void publish_meter_identity(intptr_t argument)
{
    auto *snapshot = reinterpret_cast<IdentitySnapshot *>(argument);
    if (snapshot == nullptr) {
        return;
    }
    if (snapshot->meter_id_changed) {
        esp_matter_attr_val_t value = esp_matter_char_str(
            snapshot->meter_id, strlen(snapshot->meter_id));
        const esp_err_t error = esp_matter::attribute::update(
            snapshot->endpoint_id, kSmartMeterDiagnosticsClusterId,
            kSmartMeterIdAttributeId, &value);
        if (error != ESP_OK) {
            ESP_LOGE(TAG, "Failed to publish meter ID: %s", esp_err_to_name(error));
        }
    }
    if (snapshot->manufacturer_changed) {
        esp_matter_attr_val_t value = esp_matter_char_str(
            snapshot->manufacturer, strlen(snapshot->manufacturer));
        const esp_err_t error = esp_matter::attribute::update(
            snapshot->endpoint_id, kSmartMeterDiagnosticsClusterId,
            kSmartMeterManufacturerAttributeId, &value);
        if (error != ESP_OK) {
            ESP_LOGE(TAG, "Failed to publish meter manufacturer: %s", esp_err_to_name(error));
        }
    }
    delete snapshot;
}

bool decode_identity_value(char (&output)[kMaxMeterIdentityLength + 1])
{
    uint8_t raw[kMaxMeterIdentityLength];
    size_t length = 0;
    if (!smlOBISOctetString(raw, sizeof(raw), &length)) {
        return false;
    }

    bool printable = true;
    for (size_t i = 0; i < length; ++i) {
        printable = printable && raw[i] >= 0x20 && raw[i] <= 0x7e;
    }
    if (printable) {
        memcpy(output, raw, length);
        output[length] = '\0';
    } else {
        if (length * 2 > kMaxMeterIdentityLength) {
            return false;
        }
        constexpr char kHex[] = "0123456789ABCDEF";
        for (size_t i = 0; i < length; ++i) {
            output[i * 2] = kHex[raw[i] >> 4];
            output[i * 2 + 1] = kHex[raw[i] & 0x0f];
        }
        output[length * 2] = '\0';
    }
    return true;
}

void publish_active_power_obis_seen(intptr_t argument)
{
    if (argument == 0) {
        return;
    }

    esp_matter_attr_val_t value = esp_matter_bool(true);
    const esp_err_t error = esp_matter::attribute::update(
        g_state.endpoint_id, kSmartMeterDiagnosticsClusterId,
        kSmartMeterActivePowerObisSeenAttributeId, &value);
    if (error != ESP_OK) {
        ESP_LOGE(TAG, "Failed to publish active-power OBIS diagnostic: %s",
                 esp_err_to_name(error));
    }
}

bool scale_to_milli(int64_t raw, int8_t scaler, int64_t &result)
{
    result = raw;
    int exponent = static_cast<int>(scaler) + 3;
    while (exponent > 0) {
        if (result > INT64_MAX / 10 || result < INT64_MIN / 10) {
            return false;
        }
        result *= 10;
        --exponent;
    }
    while (exponent < 0) {
        result /= 10;
        ++exponent;
    }
    return true;
}

bool should_publish(const Reading &reading, TickType_t now)
{
    if (!reading.valid) {
        return false;
    }
    const TickType_t min_interval = pdMS_TO_TICKS(CONFIG_SMARTMETER_MIN_UPDATE_INTERVAL_SECONDS * 1000ULL);
    const TickType_t max_interval = pdMS_TO_TICKS(CONFIG_SMARTMETER_MAX_UPDATE_INTERVAL_SECONDS * 1000ULL);
    const TickType_t elapsed = now - reading.last_publish_tick;
    return reading.last_publish_tick == 0 ||
           (reading.value != reading.last_published && elapsed >= min_interval) ||
           elapsed >= max_interval;
}

DataModel::Nullable<ElectricalEnergyMeasurement::Structs::EnergyMeasurementStruct::Type>
make_energy_value(bool valid, int64_t milli_watt_hours, uint64_t now_ms)
{
    if (!valid) {
        return DataModel::NullNullable;
    }
    ElectricalEnergyMeasurement::Structs::EnergyMeasurementStruct::Type value = {
        .energy = milli_watt_hours,
        .startTimestamp = NullOptional,
        .endTimestamp = NullOptional,
        .startSystime = NullOptional,
        .endSystime = MakeOptional(now_ms),
    };
    return DataModel::Nullable<ElectricalEnergyMeasurement::Structs::EnergyMeasurementStruct::Type>(value);
}

void publish_snapshot(intptr_t argument)
{
    auto *snapshot = reinterpret_cast<PublishSnapshot *>(argument);
    if (snapshot->publish_power && snapshot->power_valid) {
        CHIP_ERROR error = snapshot->delegate->SetActivePowerMilliwatts(snapshot->power);
        if (error != CHIP_NO_ERROR) {
            ESP_LOGE(TAG, "Failed to update active power: %" CHIP_ERROR_FORMAT, error.Format());
        }
    }

    if (snapshot->publish_imported || snapshot->publish_exported) {
        const uint64_t now_ms = System::SystemClock().GetMonotonicTimestamp().count();
        auto imported_value = make_energy_value(snapshot->imported_valid, snapshot->imported, now_ms);
        auto exported_value = make_energy_value(snapshot->exported_valid, snapshot->exported, now_ms);
        if (!ElectricalEnergyMeasurement::NotifyCumulativeEnergyMeasured(
                snapshot->endpoint_id, imported_value, exported_value)) {
            ESP_LOGE(TAG, "Failed to publish cumulative energy");
        }
    }

    delete snapshot;
}

void publish_readings_if_due()
{
    TickType_t now = xTaskGetTickCount();
    const bool publish_power = should_publish(g_state.power, now);
    const bool publish_imported = should_publish(g_state.imported, now);
    const bool publish_exported = should_publish(g_state.exported, now);

    if (!publish_power && !publish_imported && !publish_exported) {
        return;
    }

    const uint16_t endpoint_id = g_state.endpoint_id;
    SmartMeterPowerDelegate *delegate = g_state.power_delegate;
    const bool power_valid = g_state.power.valid;
    const int64_t power = g_state.power.value;
    const bool imported_valid = g_state.imported.valid;
    const int64_t imported = g_state.imported.value;
    const bool exported_valid = g_state.exported.valid;
    const int64_t exported = g_state.exported.value;

    if (publish_power) {
        g_state.power.last_published = power;
        g_state.power.last_publish_tick = now;
    }
    if (publish_imported) {
        g_state.imported.last_published = imported;
        g_state.imported.last_publish_tick = now;
    }
    if (publish_exported) {
        g_state.exported.last_published = exported;
        g_state.exported.last_publish_tick = now;
    }

    auto *snapshot = new (std::nothrow) PublishSnapshot{
        endpoint_id, delegate, publish_power, power_valid, power,
        publish_imported, imported_valid, imported,
        publish_exported, exported_valid, exported,
    };
    if (snapshot == nullptr) {
        ESP_LOGE(TAG, "Failed to allocate Matter publish snapshot");
        return;
    }

    CHIP_ERROR error = DeviceLayer::PlatformMgr().ScheduleWork(
        publish_snapshot, reinterpret_cast<intptr_t>(snapshot));
    if (error != CHIP_NO_ERROR) {
        ESP_LOGE(TAG, "Failed to schedule Matter update: %" CHIP_ERROR_FORMAT, error.Format());
        delete snapshot;
    }
}

void handle_list_end()
{
    if (smlOBISCheck(kMeterIdObis)) {
        g_state.pending.meter_id.valid =
            decode_identity_value(g_state.pending.meter_id.value);
    } else if (smlOBISCheck(kMeterManufacturerObis)) {
        g_state.pending.manufacturer.valid =
            decode_identity_value(g_state.pending.manufacturer.value);
    }

    for (const auto &handler : kHandlers) {
        if (!smlOBISCheck(handler.obis)) {
            continue;
        }

        int64_t raw = 0;
        signed char scaler = 0;
        smlOBISByUnit(raw, scaler, handler.unit);

        int64_t matter_value = 0;
        if (!scale_to_milli(raw, scaler, matter_value)) {
            ESP_LOGW(TAG, "Ignoring overflowing OBIS value");
            continue;
        }

        CandidateReading &reading = pending_for(handler.type);
        reading.value = matter_value;
        reading.valid = true;
        ESP_LOGI(TAG, "OBIS type=%u value=%lld", static_cast<unsigned>(handler.type),
                 static_cast<long long>(matter_value));
    }
}

void set_led_duty(uint32_t duty)
{
    if (ledc_set_duty(kLedSpeedMode, kLedChannel, duty) == ESP_OK) {
        (void) ledc_update_duty(kLedSpeedMode, kLedChannel);
    }
}

void status_led_task(void *)
{
    uint32_t breath_step = 0;
    TickType_t pulse_until = 0;

    while (true) {
        if (ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(kLedStepMs)) != 0) {
            pulse_until = xTaskGetTickCount() + pdMS_TO_TICKS(kLedReceivePulseMs);
        }

        const TickType_t now = xTaskGetTickCount();
        if (pulse_until != 0 && static_cast<int32_t>(pulse_until - now) > 0) {
            set_led_duty(kLedMaxDuty);
            continue;
        }
        pulse_until = 0;

        // Four-second, gamma-corrected breathing cycle. Its deliberately dim
        // maximum makes the full-brightness SML receive pulse easy to see.
        const uint32_t half = kLedBreathSteps / 2;
        const uint32_t linear = breath_step < half ? breath_step : kLedBreathSteps - breath_step;
        const uint32_t curved = (linear * linear * (kLedBreathMaxDuty - kLedBreathMinDuty)) /
                                (half * half);
        set_led_duty(kLedBreathMinDuty + curved);
        breath_step = (breath_step + 1) % kLedBreathSteps;
    }
}

esp_err_t start_status_led()
{
    ledc_timer_config_t timer = {};
    timer.speed_mode = kLedSpeedMode;
    timer.duty_resolution = LEDC_TIMER_10_BIT;
    timer.timer_num = kLedTimer;
    timer.freq_hz = 5000;
    timer.clk_cfg = LEDC_AUTO_CLK;
    ESP_RETURN_ON_ERROR(ledc_timer_config(&timer), TAG, "Failed to configure status LED timer");

    ledc_channel_config_t channel = {};
    channel.gpio_num = CONFIG_SMARTMETER_LED_GPIO;
    channel.speed_mode = kLedSpeedMode;
    channel.channel = kLedChannel;
    channel.intr_type = LEDC_INTR_DISABLE;
    channel.timer_sel = kLedTimer;
    channel.duty = 0;
    channel.hpoint = 0;
#if CONFIG_SMARTMETER_LED_ACTIVE_LOW
    channel.flags.output_invert = 1;
#endif
    ESP_RETURN_ON_ERROR(ledc_channel_config(&channel), TAG,
                        "Failed to configure status LED channel");

    const BaseType_t created = xTaskCreate(status_led_task, "status_led", 2048, nullptr, 2,
                                           &g_led_task_handle);
    ESP_RETURN_ON_FALSE(created == pdPASS, ESP_ERR_NO_MEM, TAG,
                        "Failed to create status LED task");
    return ESP_OK;
}

void notify_sml_frame_received()
{
    if (g_led_task_handle != nullptr) {
        xTaskNotifyGive(g_led_task_handle);
    }
}

void smart_meter_task(void *)
{
    uint8_t buffer[256];

    while (true) {
        xSemaphoreTake(g_uart_mutex, portMAX_DELAY);
        const int length = uart_read_bytes(static_cast<uart_port_t>(CONFIG_SMARTMETER_UART_NUM), buffer,
                                           sizeof(buffer), pdMS_TO_TICKS(250));
        xSemaphoreGive(g_uart_mutex);
        if (length <= 0) {
            continue;
        }

        for (int i = 0; i < length; ++i) {
            unsigned char byte = buffer[i];
            const sml_states_t state = smlState(byte);
            if (state == SML_VERSION) {
                g_state.pending = {};
            } else if (state == SML_LISTEND) {
                handle_list_end();
            } else if (state == SML_FINAL) {
                const bool had_active_power_obis = g_state.power.valid;
                const uint8_t identity_changes = commit_pending_frame();
                if (identity_changes != 0) {
                    auto *snapshot = new (std::nothrow) IdentitySnapshot{};
                    if (snapshot != nullptr) {
                        snapshot->endpoint_id = g_state.endpoint_id;
                        snapshot->meter_id_changed = (identity_changes & 1) != 0;
                        snapshot->manufacturer_changed = (identity_changes & 2) != 0;
                        memcpy(snapshot->meter_id, g_state.meter_id.value, sizeof(snapshot->meter_id));
                        memcpy(snapshot->manufacturer, g_state.manufacturer.value,
                               sizeof(snapshot->manufacturer));
                        const CHIP_ERROR error = DeviceLayer::PlatformMgr().ScheduleWork(
                            publish_meter_identity, reinterpret_cast<intptr_t>(snapshot));
                        if (error != CHIP_NO_ERROR) {
                            ESP_LOGE(TAG, "Failed to schedule meter identity update: %" CHIP_ERROR_FORMAT,
                                     error.Format());
                            delete snapshot;
                        }
                    } else {
                        ESP_LOGE(TAG, "Out of memory publishing meter identity");
                    }
                }
                if (!had_active_power_obis && g_state.power.valid) {
                    // Matter attribute changes must be published from the
                    // Matter platform work queue, not the UART task.
                    CHIP_ERROR error = DeviceLayer::PlatformMgr().ScheduleWork(
                        publish_active_power_obis_seen, 1);
                    if (error != CHIP_NO_ERROR) {
                        ESP_LOGE(TAG, "Failed to schedule active-power OBIS diagnostic: %" CHIP_ERROR_FORMAT,
                                 error.Format());
                    }
                }
                notify_sml_frame_received();
                publish_readings_if_due();
            } else if (state == SML_CHECKSUM_ERROR) {
                g_state.pending = {};
                ESP_LOGW(TAG, "Discarded SML frame with invalid CRC");
            }
        }
    }
}

esp_err_t transmit_ir_flash(uint32_t duration_ms)
{
    // A UART 0x00 byte keeps TX active for the start bit and all eight data
    // bits, with only the stop bit inactive. Repeating it therefore produces
    // a stable 90%-duty optical burst while preserving normal UART idle state.
    const uart_port_t port = static_cast<uart_port_t>(CONFIG_SMARTMETER_UART_NUM);
    const uint64_t numerator =
        static_cast<uint64_t>(duration_ms) * CONFIG_SMARTMETER_UART_BAUD;
    size_t remaining = static_cast<size_t>((numerator + 9'999) / 10'000);
    if (remaining == 0) {
        remaining = 1;
    }

    uint8_t active_bytes[64] = {};
    while (remaining != 0) {
        const size_t chunk = remaining < sizeof(active_bytes) ? remaining : sizeof(active_bytes);
        const int written = uart_write_bytes(port, active_bytes, chunk);
        if (written != static_cast<int>(chunk)) {
            return ESP_FAIL;
        }
        remaining -= chunk;
    }

    return uart_wait_tx_done(port, pdMS_TO_TICKS(duration_ms + 1000));
}

esp_err_t send_short_flash()
{
    ESP_RETURN_ON_ERROR(transmit_ir_flash(CONFIG_SMARTMETER_PIN_SHORT_FLASH_MS), TAG,
                        "IR flash failed");
    vTaskDelay(pdMS_TO_TICKS(CONFIG_SMARTMETER_PIN_FLASH_GAP_MS));
    return ESP_OK;
}

esp_err_t transmit_pin(const PinRequest &request)
{
    // Netze Duisburg specifies two short optical activations before the meter
    // presents the first zero of its PIN entry display.
    for (unsigned activation = 0; activation < 2; ++activation) {
        ESP_RETURN_ON_ERROR(send_short_flash(), TAG, "PIN-entry activation failed");
    }
    vTaskDelay(pdMS_TO_TICKS(CONFIG_SMARTMETER_PIN_WAKE_SETTLE_MS));

    for (char digit_char : request.digits) {
        const unsigned digit = static_cast<unsigned>(digit_char - '0');
        for (unsigned count = 0; count < digit; ++count) {
            ESP_RETURN_ON_ERROR(send_short_flash(), TAG, "PIN digit transmission failed");
        }
        // The meter advances to the next digit after at least three seconds
        // without light. A zero is entered by sending no flash in this period.
        vTaskDelay(pdMS_TO_TICKS(CONFIG_SMARTMETER_PIN_DIGIT_WAIT_MS));
    }
    return ESP_OK;
}

void pin_transmitter_task(void *)
{
    PinRequest request = {};
    while (true) {
        if (xQueueReceive(g_pin_queue, &request, portMAX_DELAY) != pdTRUE) {
            continue;
        }

        ESP_LOGI(TAG, "Starting optical meter PIN entry");
        xSemaphoreTake(g_uart_mutex, portMAX_DELAY);
        uart_flush_input(static_cast<uart_port_t>(CONFIG_SMARTMETER_UART_NUM));
        const esp_err_t error = transmit_pin(request);
        uart_flush_input(static_cast<uart_port_t>(CONFIG_SMARTMETER_UART_NUM));
        xSemaphoreGive(g_uart_mutex);

        memset(&request, 0, sizeof(request));
        g_pin_busy.store(false);
        if (error == ESP_OK) {
            ESP_LOGI(TAG, "Optical meter PIN entry complete");
        } else {
            ESP_LOGE(TAG, "Optical meter PIN entry failed: %s", esp_err_to_name(error));
        }
    }
}

int meter_pin_console_command(int argc, char **argv)
{
    if (argc != 2) {
        printf("Usage: meter-pin <4 digits>\n");
        return 1;
    }

    const esp_err_t error = smart_meter_submit_pin(argv[1]);
    if (error != ESP_OK) {
        printf("PIN request rejected: %s\n", esp_err_to_name(error));
        return 1;
    }
    printf("PIN request accepted; watch the meter display.\n");
    return 0;
}
} // namespace

esp_err_t smart_meter_start(uint16_t matter_endpoint_id, SmartMeterPowerDelegate *power_delegate)
{
    ESP_RETURN_ON_FALSE(power_delegate != nullptr, ESP_ERR_INVALID_ARG, TAG, "Power delegate is null");

    g_state.endpoint_id = matter_endpoint_id;
    g_state.power_delegate = power_delegate;

    ESP_RETURN_ON_ERROR(start_status_led(), TAG, "Failed to start status LED");

    uart_config_t uart_config = {};
    uart_config.baud_rate = CONFIG_SMARTMETER_UART_BAUD;
    uart_config.data_bits = UART_DATA_8_BITS;
    uart_config.parity = UART_PARITY_DISABLE;
    uart_config.stop_bits = UART_STOP_BITS_1;
    uart_config.flow_ctrl = UART_HW_FLOWCTRL_DISABLE;
    uart_config.source_clk = UART_SCLK_DEFAULT;

    const uart_port_t port = static_cast<uart_port_t>(CONFIG_SMARTMETER_UART_NUM);
    ESP_RETURN_ON_ERROR(uart_driver_install(port, 4096, 0, 0, nullptr, 0), TAG,
                        "Failed to install UART driver");
    ESP_RETURN_ON_ERROR(uart_param_config(port, &uart_config), TAG, "Failed to configure UART");
    ESP_RETURN_ON_ERROR(uart_set_pin(port, CONFIG_SMARTMETER_UART_TX_GPIO,
                                     CONFIG_SMARTMETER_UART_RX_GPIO,
                                     UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE),
                        TAG, "Failed to assign UART pins");
#if CONFIG_SMARTMETER_IR_TX_INVERTED
    ESP_RETURN_ON_ERROR(uart_set_line_inverse(port, UART_SIGNAL_TXD_INV), TAG,
                        "Failed to invert UART TX");
#endif

    g_uart_mutex = xSemaphoreCreateMutex();
    ESP_RETURN_ON_FALSE(g_uart_mutex != nullptr, ESP_ERR_NO_MEM, TAG,
                        "Failed to create UART mutex");
    g_pin_queue = xQueueCreate(1, sizeof(PinRequest));
    ESP_RETURN_ON_FALSE(g_pin_queue != nullptr, ESP_ERR_NO_MEM, TAG,
                        "Failed to create PIN queue");

    BaseType_t created = xTaskCreate(smart_meter_task, "sml_reader", 6144, nullptr, 5, nullptr);
    ESP_RETURN_ON_FALSE(created == pdPASS, ESP_ERR_NO_MEM, TAG, "Failed to create SML task");
    created = xTaskCreate(pin_transmitter_task, "pin_transmitter", 4096, nullptr, 5, nullptr);
    ESP_RETURN_ON_FALSE(created == pdPASS, ESP_ERR_NO_MEM, TAG,
                        "Failed to create PIN transmitter task");
    return ESP_OK;
}

esp_err_t smart_meter_submit_pin(const char *pin)
{
    ESP_RETURN_ON_FALSE(pin != nullptr, ESP_ERR_INVALID_ARG, TAG, "PIN is null");
    ESP_RETURN_ON_FALSE(strlen(pin) == 4, ESP_ERR_INVALID_ARG, TAG,
                        "PIN must contain four digits");

    bool any_nonzero = false;
    for (size_t index = 0; index < 4; ++index) {
        ESP_RETURN_ON_FALSE(isdigit(static_cast<unsigned char>(pin[index])),
                            ESP_ERR_INVALID_ARG, TAG, "PIN must contain only digits");
        any_nonzero = any_nonzero || pin[index] != '0';
    }
    ESP_RETURN_ON_FALSE(any_nonzero, ESP_ERR_INVALID_ARG, TAG,
                        "Meter PIN 0000 is not valid");
    ESP_RETURN_ON_FALSE(g_pin_queue != nullptr, ESP_ERR_INVALID_STATE, TAG,
                        "PIN transmitter is not initialized");

    bool expected = false;
    ESP_RETURN_ON_FALSE(g_pin_busy.compare_exchange_strong(expected, true),
                        ESP_ERR_INVALID_STATE, TAG, "PIN transmitter is busy");

    PinRequest request = {};
    memcpy(request.digits, pin, sizeof(request.digits));
    if (xQueueSend(g_pin_queue, &request, 0) != pdTRUE) {
        g_pin_busy.store(false);
        memset(&request, 0, sizeof(request));
        return ESP_ERR_TIMEOUT;
    }

    memset(&request, 0, sizeof(request));
    return ESP_OK;
}

esp_err_t smart_meter_register_console_commands()
{
    esp_console_cmd_t command = {};
    command.command = "meter-pin";
    command.help = "Enter a four-digit meter PIN through the IR head";
    command.hint = "<4 digits>";
    command.func = meter_pin_console_command;
    return esp_console_cmd_register(&command);
}
