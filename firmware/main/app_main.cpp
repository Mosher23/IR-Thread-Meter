#include "app_openthread_config.h"
#include "electrical_meter_delegate.h"
#include "meter_pin_delegate.h"
#include "smart_meter.h"
#include "board_config.h"

#include <app/server/CommissioningWindowManager.h>
#include <app/server/Server.h>
#include <app/data-model/List.h>
#include <data_model_provider/clusters/electrical_energy_measurement/integration.h>
#include <driver/gpio.h>
#include <esp_err.h>
#include <esp_log.h>
#include <esp_ota_ops.h>
#include <esp_matter.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <nvs_flash.h>
#include <platform/CHIPDeviceLayer.h>
#if CHIP_DEVICE_CONFIG_ENABLE_THREAD
#include <platform/ESP32/OpenthreadLauncher.h>
#endif
#include <cstdio>
#include <cstdlib>
#include <atomic>

using namespace chip;
using namespace chip::app;
using namespace chip::app::Clusters;
using namespace esp_matter;

namespace {
constexpr char TAG[] = "matter_smartmeter";

SmartMeterPowerDelegate g_power_delegate;
MeterPinDelegate g_pin_delegate;
uint16_t g_meter_endpoint_id = 0;
bool g_external_antenna = false;
std::atomic<bool> g_energy_initialized{false};

esp_err_t attribute_update_cb(attribute::callback_type_t, uint16_t, uint32_t, uint32_t,
                              esp_matter_attr_val_t *, void *)
{
    return ESP_OK;
}

esp_err_t identification_cb(identification::callback_type_t type, uint16_t endpoint_id,
                            uint8_t effect_id, uint8_t effect_variant, void *)
{
    ESP_LOGI(TAG, "Identify endpoint=%u type=%u effect=%u variant=%u", endpoint_id,
             static_cast<unsigned>(type), effect_id, effect_variant);
    return ESP_OK;
}

void open_commissioning_window_if_needed()
{
    if (chip::Server::GetInstance().GetFabricTable().FabricCount() != 0) {
        return;
    }

    chip::CommissioningWindowManager &manager =
        chip::Server::GetInstance().GetCommissioningWindowManager();
    if (manager.IsCommissioningWindowOpen()) {
        return;
    }

    CHIP_ERROR error = manager.OpenBasicCommissioningWindow(
        chip::System::Clock::Seconds16(300),
        chip::CommissioningWindowAdvertisement::kDnssdOnly);
    if (error != CHIP_NO_ERROR) {
        ESP_LOGE(TAG, "Failed to open commissioning window: %" CHIP_ERROR_FORMAT,
                 error.Format());
    }
}

void configure_rf_antenna()
{
    const gpio_num_t enable_gpio =
        static_cast<gpio_num_t>(CONFIG_SMARTMETER_RF_SWITCH_ENABLE_GPIO);
    const gpio_num_t select_gpio =
        static_cast<gpio_num_t>(CONFIG_SMARTMETER_RF_SWITCH_SELECT_GPIO);

    ESP_ERROR_CHECK(gpio_reset_pin(enable_gpio));
    ESP_ERROR_CHECK(gpio_set_direction(enable_gpio, GPIO_MODE_OUTPUT));
    ESP_ERROR_CHECK(gpio_set_level(enable_gpio, 0));

    // Seeed specifies enabling RF-switch control on GPIO3 before selecting
    // the antenna with GPIO14.
    vTaskDelay(pdMS_TO_TICKS(100));

    ESP_ERROR_CHECK(gpio_reset_pin(select_gpio));
    ESP_ERROR_CHECK(gpio_set_direction(select_gpio, GPIO_MODE_OUTPUT));
    ESP_ERROR_CHECK(gpio_set_level(select_gpio, g_external_antenna ? 1 : 0));
    ESP_LOGI(TAG, "Saved RF antenna: %s", g_external_antenna ? "external" : "internal");
}

void matter_event_cb(const ChipDeviceEvent *event, intptr_t)
{
    switch (event->Type) {
    case DeviceLayer::DeviceEventType::kCommissioningComplete:
        ESP_LOGI(TAG, "Matter commissioning complete");
        break;
    case DeviceLayer::DeviceEventType::kFailSafeTimerExpired:
        ESP_LOGW(TAG, "Matter commissioning failed: fail-safe timer expired");
        break;
    case DeviceLayer::DeviceEventType::kFabricRemoved:
        ESP_LOGI(TAG, "Matter fabric removed");
        open_commissioning_window_if_needed();
        break;
    case DeviceLayer::DeviceEventType::kBLEDeinitialized:
        ESP_LOGI(TAG, "BLE commissioning memory reclaimed");
        break;
    default:
        break;
    }
}

void initialize_energy_cluster(intptr_t argument)
{
    const EndpointId endpoint_id = static_cast<EndpointId>(argument);

    static const ElectricalEnergyMeasurement::Structs::MeasurementAccuracyRangeStruct::Type
        accuracy_ranges[] = {
            {
                .rangeMin = 0,
                .rangeMax = 1'000'000'000'000'000LL,
                .percentMax = MakeOptional(static_cast<Percent100ths>(100)),
                .percentMin = NullOptional,
                .percentTypical = NullOptional,
                .fixedMax = NullOptional,
                .fixedMin = NullOptional,
                .fixedTypical = NullOptional,
            },
        };

    ElectricalEnergyMeasurement::Structs::MeasurementAccuracyStruct::Type accuracy = {
        .measurementType = ElectricalEnergyMeasurement::MeasurementTypeEnum::kElectricalEnergy,
        .measured = true,
        .minMeasuredValue = 0,
        .maxMeasuredValue = 1'000'000'000'000'000LL,
        .accuracyRanges = DataModel::List<const ElectricalEnergyMeasurement::Structs::MeasurementAccuracyRangeStruct::Type>(accuracy_ranges),
    };

    CHIP_ERROR error = ElectricalEnergyMeasurement::SetMeasurementAccuracy(endpoint_id, accuracy);
    if (error != CHIP_NO_ERROR) {
        ESP_LOGE(TAG, "Failed to initialize energy accuracy: %" CHIP_ERROR_FORMAT,
                 error.Format());
    } else {
        g_energy_initialized.store(true);
    }
}

void ota_health_task(void *)
{
    // Startup must survive 30 seconds with Matter and the SML task started.
    // A missing meter or temporarily unavailable Thread network is NOT a fault.
    vTaskDelay(pdMS_TO_TICKS(30000));
    esp_ota_img_states_t state;
    const esp_partition_t *running = esp_ota_get_running_partition();
    if (running && esp_ota_get_state_partition(running, &state) == ESP_OK &&
        state == ESP_OTA_IMG_PENDING_VERIFY) {
        if (!g_energy_initialized.load()) {
            ESP_LOGE(TAG, "OTA startup health check failed; rolling back");
            ESP_ERROR_CHECK(esp_ota_mark_app_invalid_rollback_and_reboot());
        }
        ESP_ERROR_CHECK(esp_ota_mark_app_valid_cancel_rollback());
        ESP_LOGI(TAG, "OTA startup health check passed");
    }
    vTaskDelete(nullptr);
}

void factory_reset_button_task(void *)
{
    gpio_config_t config = {};
    config.pin_bit_mask = 1ULL << CONFIG_SMARTMETER_FACTORY_RESET_GPIO;
    config.mode = GPIO_MODE_INPUT;
    config.pull_up_en = GPIO_PULLUP_ENABLE;
    ESP_ERROR_CHECK(gpio_config(&config));

    TickType_t pressed_since = 0;
    while (true) {
        const bool pressed = gpio_get_level(
                                 static_cast<gpio_num_t>(CONFIG_SMARTMETER_FACTORY_RESET_GPIO)) == 0;
        if (pressed) {
            if (pressed_since == 0) {
                pressed_since = xTaskGetTickCount();
            } else if ((xTaskGetTickCount() - pressed_since) >= pdMS_TO_TICKS(5000)) {
                ESP_LOGW(TAG, "Factory reset requested");
                esp_matter::factory_reset();
                vTaskDelete(nullptr);
            }
        } else {
            pressed_since = 0;
        }
        vTaskDelay(pdMS_TO_TICKS(50));
    }
}
} // namespace

extern "C" void app_main()
{
    g_external_antenna = board_config_init();
    configure_rf_antenna();

    esp_err_t error = nvs_flash_init();
    // Do not erase pairings automatically on a failed NVS migration.
    ESP_ERROR_CHECK(error);

    node::config_t node_config;
    std::snprintf(node_config.root_node.basic_information.node_label,
                  sizeof(node_config.root_node.basic_information.node_label),
                  "%s", CHIP_DEVICE_CONFIG_DEVICE_NAME);
    node_t *node = node::create(&node_config, attribute_update_cb, identification_cb);
    if (node == nullptr) {
        ESP_LOGE(TAG, "Failed to create Matter node");
        abort();
    }

    // SerialNumber is optional in Matter Basic Information. Enable the
    // attribute so the configured device-instance serial is exposed to
    // commissioners and controllers.
    cluster_t *basic_information_cluster =
        cluster::get(static_cast<uint16_t>(0), BasicInformation::Id);
    if (basic_information_cluster == nullptr ||
        cluster::basic_information::attribute::create_serial_number(
            basic_information_cluster, nullptr, 0) == nullptr) {
        ESP_LOGE(TAG, "Failed to enable Basic Information serial number");
        abort();
    }

    endpoint::electrical_meter::config_t meter_config;
    meter_config.electrical_power_measurement.delegate = &g_power_delegate;
    meter_config.electrical_power_measurement.feature_flags =
        cluster::electrical_power_measurement::feature::alternating_current::get_id();
    meter_config.electrical_energy_measurement.feature_flags =
        cluster::electrical_energy_measurement::feature::imported_energy::get_id() |
        cluster::electrical_energy_measurement::feature::exported_energy::get_id() |
        cluster::electrical_energy_measurement::feature::cumulative_energy::get_id();

    endpoint_t *meter_endpoint =
        endpoint::electrical_meter::create(node, &meter_config, ENDPOINT_FLAG_NONE, nullptr);
    if (meter_endpoint == nullptr) {
        ESP_LOGE(TAG, "Failed to create Matter Electrical Meter endpoint");
        abort();
    }
    g_meter_endpoint_id = endpoint::get_id(meter_endpoint);

    // This deliberately is a vendor-specific, read-only Matter diagnostic.
    // A controller that does not know this cluster safely ignores it; the
    // companion Home Assistant integration exposes it as a diagnostic binary
    // sensor named "Active-power OBIS received".
    cluster_t *diagnostics_cluster =
        cluster::create(meter_endpoint, kSmartMeterDiagnosticsClusterId, CLUSTER_FLAG_SERVER);
    static char empty_meter_identity[] = "";
    if (diagnostics_cluster == nullptr ||
        attribute::create(diagnostics_cluster, 3, ATTRIBUTE_FLAG_NONE,
                          esp_matter_bool(g_external_antenna)) == nullptr ||
        attribute::create(diagnostics_cluster, 4, ATTRIBUTE_FLAG_NONE,
                          esp_matter_bool(true)) == nullptr ||
        attribute::create(diagnostics_cluster, kSmartMeterActivePowerObisSeenAttributeId,
                          ATTRIBUTE_FLAG_NONE, esp_matter_bool(false)) == nullptr ||
        attribute::create(diagnostics_cluster, kSmartMeterIdAttributeId,
                          ATTRIBUTE_FLAG_NONE,
                          esp_matter_char_str(empty_meter_identity, 0),
                          kSmartMeterIdentityMaxLength) == nullptr ||
        attribute::create(diagnostics_cluster, kSmartMeterManufacturerAttributeId,
                          ATTRIBUTE_FLAG_NONE,
                          esp_matter_char_str(empty_meter_identity, 0),
                          kSmartMeterIdentityMaxLength) == nullptr) {
        ESP_LOGE(TAG, "Failed to create smart-meter diagnostics cluster");
        abort();
    }

    cluster::keypad_input::config_t keypad_config;
    keypad_config.delegate = &g_pin_delegate;
    cluster_t *keypad_cluster = cluster::keypad_input::create(
        meter_endpoint, &keypad_config, CLUSTER_FLAG_SERVER);
    if (keypad_cluster == nullptr ||
        cluster::keypad_input::feature::number_keys::add(keypad_cluster) != ESP_OK) {
        ESP_LOGE(TAG, "Failed to create Matter PIN-input cluster");
        abort();
    }

#if CHIP_DEVICE_CONFIG_ENABLE_THREAD
    esp_openthread_platform_config_t thread_config = {
        .radio_config = ESP_OPENTHREAD_DEFAULT_RADIO_CONFIG(),
        .host_config = ESP_OPENTHREAD_DEFAULT_HOST_CONFIG(),
        .port_config = ESP_OPENTHREAD_DEFAULT_PORT_CONFIG(),
    };
    set_openthread_platform_config(&thread_config);
#else
#error "This application requires Matter over Thread"
#endif

    error = esp_matter::start(matter_event_cb);
    if (error != ESP_OK) {
        ESP_LOGE(TAG, "Failed to start Matter: %s", esp_err_to_name(error));
        abort();
    }

    CHIP_ERROR schedule_error = DeviceLayer::PlatformMgr().ScheduleWork(
        initialize_energy_cluster, static_cast<intptr_t>(g_meter_endpoint_id));
    if (schedule_error != CHIP_NO_ERROR) {
        ESP_LOGE(TAG, "Failed to schedule energy-cluster initialization: %" CHIP_ERROR_FORMAT,
                 schedule_error.Format());
        abort();
    }

    error = smart_meter_start(g_meter_endpoint_id, &g_power_delegate);
    if (error != ESP_OK) {
        ESP_LOGE(TAG, "Failed to start SML reader: %s", esp_err_to_name(error));
        abort();
    }

    error = smart_meter_register_console_commands();
    if (error != ESP_OK) {
        ESP_LOGW(TAG, "Failed to register meter-pin console command: %s",
                 esp_err_to_name(error));
    }

    if (xTaskCreate(factory_reset_button_task, "factory_reset", 3072, nullptr, 3,
                    nullptr) != pdPASS) {
        ESP_LOGE(TAG, "Failed to create factory-reset button task");
        abort();
    }

    if (xTaskCreate(ota_health_task, "ota_health", 3072, nullptr, 3, nullptr) != pdPASS) {
        abort();
    }

    ESP_LOGI(TAG, "Matter-over-Thread smart meter ready on endpoint %u",
             g_meter_endpoint_id);
}
