#pragma once

#include <app/clusters/power-topology-server/PowerTopologyDelegate.h>

// TreeTopology uses Descriptor composition, not endpoint sets. The meter has
// no child endpoints; its sibling antenna control is outside the measurement.
// Keep a delegate for the SDK lifecycle without advertising optional lists.
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
