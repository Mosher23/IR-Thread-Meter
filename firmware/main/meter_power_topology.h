#pragma once

#include <app/clusters/power-topology-server/PowerTopologyDelegate.h>

// NodeTopology describes whole-device measurements. Its optional endpoint
// lists are not advertised; keep a delegate for the SDK server's lifecycle.
class MeterPowerTopologyDelegate final
    : public chip::app::Clusters::PowerTopology::Delegate {
public:
    CHIP_ERROR GetAvailableEndpointAtIndex(size_t, chip::EndpointId &) override
    {
        return CHIP_ERROR_PROVIDER_LIST_EXHAUSTED;
    }

    CHIP_ERROR GetActiveEndpointAtIndex(size_t, chip::EndpointId &) override
    {
        return CHIP_ERROR_PROVIDER_LIST_EXHAUSTED;
    }
};
