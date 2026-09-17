#include "meter_pin_delegate.h"

#include "smart_meter.h"

#include <esp_log.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <string.h>

using namespace chip;
using namespace chip::app;
using namespace chip::app::Clusters;

namespace {
constexpr char TAG[] = "meter_pin";
constexpr uint32_t kEntryTimeoutMs = 30'000;

bool key_to_digit(KeypadInput::CECKeyCodeEnum key_code, char &digit)
{
    switch (key_code) {
    case KeypadInput::CECKeyCodeEnum::kNumber0OrNumber10:
        digit = '0';
        return true;
    case KeypadInput::CECKeyCodeEnum::kNumbers1:
        digit = '1';
        return true;
    case KeypadInput::CECKeyCodeEnum::kNumbers2:
        digit = '2';
        return true;
    case KeypadInput::CECKeyCodeEnum::kNumbers3:
        digit = '3';
        return true;
    case KeypadInput::CECKeyCodeEnum::kNumbers4:
        digit = '4';
        return true;
    case KeypadInput::CECKeyCodeEnum::kNumbers5:
        digit = '5';
        return true;
    case KeypadInput::CECKeyCodeEnum::kNumbers6:
        digit = '6';
        return true;
    case KeypadInput::CECKeyCodeEnum::kNumbers7:
        digit = '7';
        return true;
    case KeypadInput::CECKeyCodeEnum::kNumbers8:
        digit = '8';
        return true;
    case KeypadInput::CECKeyCodeEnum::kNumbers9:
        digit = '9';
        return true;
    default:
        return false;
    }
}

void send_response(
    CommandResponseHelper<KeypadInput::Commands::SendKeyResponse::Type> &helper,
    KeypadInput::StatusEnum status)
{
    KeypadInput::Commands::SendKeyResponse::Type response;
    response.status = status;
    (void) helper.Success(response);
}
} // namespace

void MeterPinDelegate::ResetEntry()
{
    memset(m_digits, 0, sizeof(m_digits));
    m_digit_count = 0;
    m_started_at_ms = 0;
}

void MeterPinDelegate::HandleSendKey(
    CommandResponseHelper<KeypadInput::Commands::SendKeyResponse::Type> &helper,
    const KeypadInput::CECKeyCodeEnum &key_code)
{
    const uint32_t now_ms = xTaskGetTickCount() * portTICK_PERIOD_MS;
    if (m_digit_count != 0 && (now_ms - m_started_at_ms) > kEntryTimeoutMs) {
        ResetEntry();
    }

    if (key_code == KeypadInput::CECKeyCodeEnum::kClear ||
        key_code == KeypadInput::CECKeyCodeEnum::kExit) {
        ResetEntry();
        send_response(helper, KeypadInput::StatusEnum::kSuccess);
        return;
    }

    if (key_code == KeypadInput::CECKeyCodeEnum::kEnter ||
        key_code == KeypadInput::CECKeyCodeEnum::kSelect) {
        if (m_digit_count != 4) {
            send_response(helper, KeypadInput::StatusEnum::kInvalidKeyInCurrentState);
            return;
        }

        const esp_err_t error = smart_meter_submit_pin(m_digits);
        ResetEntry();
        if (error == ESP_OK) {
            ESP_LOGI(TAG, "Optical PIN entry accepted");
            send_response(helper, KeypadInput::StatusEnum::kSuccess);
        } else {
            ESP_LOGW(TAG, "Optical PIN entry rejected: %s", esp_err_to_name(error));
            send_response(helper, KeypadInput::StatusEnum::kInvalidKeyInCurrentState);
        }
        return;
    }

    char digit = 0;
    if (!key_to_digit(key_code, digit)) {
        send_response(helper, KeypadInput::StatusEnum::kUnsupportedKey);
        return;
    }
    if (m_digit_count >= 4) {
        send_response(helper, KeypadInput::StatusEnum::kInvalidKeyInCurrentState);
        return;
    }

    if (m_digit_count == 0) {
        m_started_at_ms = now_ms;
    }
    m_digits[m_digit_count++] = digit;
    send_response(helper, KeypadInput::StatusEnum::kSuccess);
}

uint32_t MeterPinDelegate::GetFeatureMap(chip::EndpointId)
{
    return static_cast<uint32_t>(KeypadInput::Feature::kNumberKeys);
}
