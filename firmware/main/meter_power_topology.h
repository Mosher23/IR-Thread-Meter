#pragma once

#include <app/clusters/power-topology-server/PowerTopologyDelegate.h>

// Associate the existing SML measurements with the one controllable outlet.
// The outlet's OnOff attribute selects an antenna; it does not stop the meter
// measuring. In particular, this association must not depend on that attribute.
class MeterPowerTopologyDelegate final
    : public chip::app::Clusters::PowerTopology::Delegate {
public:
    void SetOutletEndpoint(chip::EndpointId endpoint) { mOutletEndpoint = endpoint; }

    CHIP_ERROR GetAvailableEndpointAtIndex(size_t index, chip::EndpointId &endpoint) override
    {
        if (index != 0 || mOutletEndpoint == chip::kInvalidEndpointId) {
            return CHIP_ERROR_PROVIDER_LIST_EXHAUSTED;
        }
        endpoint = mOutletEndpoint;
        return CHIP_NO_ERROR;
    }

    CHIP_ERROR GetActiveEndpointAtIndex(size_t, chip::EndpointId &) override
    {
        // Static SetTopology only: no DynamicPowerFlow or ActiveEndpoints.
        return CHIP_ERROR_PROVIDER_LIST_EXHAUSTED;
    }

private:
    chip::EndpointId mOutletEndpoint = chip::kInvalidEndpointId;
};
