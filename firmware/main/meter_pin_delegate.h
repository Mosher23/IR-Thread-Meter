#pragma once

#include <app/clusters/keypad-input-server/keypad-input-delegate.h>
#include <stddef.h>
#include <stdint.h>

class MeterPinDelegate final : public chip::app::Clusters::KeypadInput::Delegate {
public:
    void HandleSendKey(
        chip::app::CommandResponseHelper<
            chip::app::Clusters::KeypadInput::Commands::SendKeyResponse::Type> &helper,
        const chip::app::Clusters::KeypadInput::CECKeyCodeEnum &key_code) override;

    uint32_t GetFeatureMap(chip::EndpointId endpoint) override;

private:
    void ResetEntry();

    char m_digits[5] = {};
    size_t m_digit_count = 0;
    uint32_t m_started_at_ms = 0;
};
