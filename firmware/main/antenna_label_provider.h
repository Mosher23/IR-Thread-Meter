#pragma once

#include <lib/support/CHIPMem.h>
#include <platform/DeviceInfoProvider.h>

// Only supplies the antenna endpoint's descriptive label. In particular this
// does not enable ESP32 factory-data credentials or change attestation, serial
// number, passcode or the commissioning provider used by existing boards.
class AntennaLabelProvider final : public chip::DeviceLayer::DeviceInfoProvider
{
public:
    explicit AntennaLabelProvider(chip::EndpointId endpoint) : mEndpoint(endpoint) {}

    FixedLabelIterator *IterateFixedLabel(chip::EndpointId endpoint) override
    {
        return chip::Platform::New<LabelIterator>(endpoint == mEndpoint);
    }

    UserLabelIterator *IterateUserLabel(chip::EndpointId) override { return nullptr; }
    SupportedLocalesIterator *IterateSupportedLocales() override { return nullptr; }
    SupportedCalendarTypesIterator *IterateSupportedCalendarTypes() override { return nullptr; }

protected:
    CHIP_ERROR SetUserLabelAt(chip::EndpointId, size_t, const UserLabelType &) override
    { return CHIP_ERROR_NOT_IMPLEMENTED; }
    CHIP_ERROR DeleteUserLabelAt(chip::EndpointId, size_t) override
    { return CHIP_ERROR_NOT_IMPLEMENTED; }
    CHIP_ERROR SetUserLabelLength(chip::EndpointId, size_t) override
    { return CHIP_ERROR_NOT_IMPLEMENTED; }
    CHIP_ERROR GetUserLabelLength(chip::EndpointId, size_t &length) override
    { length = 0; return CHIP_NO_ERROR; }

private:
    class LabelIterator final : public FixedLabelIterator
    {
    public:
        explicit LabelIterator(bool matches) : mMatches(matches) {}
        size_t Count() override { return mMatches ? 1 : 0; }
        bool Next(FixedLabelType &value) override
        {
            if (!mMatches || mRead) {
                return false;
            }
            value.label = chip::CharSpan::fromCharString("name");
            value.value = chip::CharSpan::fromCharString("External antenna");
            mRead = true;
            return true;
        }
        void Release() override { chip::Platform::Delete(this); }
    private:
        bool mMatches;
        bool mRead = false;
    };
    chip::EndpointId mEndpoint;
};
