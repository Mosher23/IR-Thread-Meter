#pragma once

#include <esp_err.h>
#include <stdint.h>

class SmartMeterPowerDelegate;

// Vendor-specific Matter diagnostics. The custom Home Assistant integration
// uses this read-only Boolean attribute to distinguish "no active-power OBIS
// has arrived" from an actual zero-watt reading.
constexpr uint32_t kSmartMeterDiagnosticsClusterId = 0xFFF1FC01;
constexpr uint32_t kSmartMeterActivePowerObisSeenAttributeId = 0x00000000;
constexpr uint32_t kSmartMeterIdAttributeId = 0x00000001;
constexpr uint32_t kSmartMeterManufacturerAttributeId = 0x00000002;
constexpr uint32_t kSmartMeterExternalAntennaAttributeId = 0x00000003;
constexpr uint32_t kSmartMeterOtaReadyAttributeId = 0x00000004;
constexpr uint16_t kSmartMeterIdentityMaxLength = 64;

esp_err_t smart_meter_start(uint16_t matter_endpoint_id, SmartMeterPowerDelegate *power_delegate);
esp_err_t smart_meter_submit_pin(const char *pin);
esp_err_t smart_meter_submit_pulse(bool long_pulse);
esp_err_t smart_meter_register_console_commands();
