"""Check the actual topology delegate and keep metering on its existing endpoint."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MeterPowerTopologyTests(unittest.TestCase):
    def test_measurements_are_associated_without_duplicate_clusters(self):
        source = (ROOT / "firmware/main/app_main.cpp").read_text()
        # Preserve the existing endpoint creation order and HA attribute paths.
        self.assertEqual(source.count("endpoint::electrical_meter::create("), 1)
        self.assertEqual(source.count("endpoint::on_off_plug_in_unit::create("), 1)
        self.assertLess(source.index("endpoint::electrical_meter::create("),
                        source.index("endpoint::on_off_plug_in_unit::create("))
        self.assertIn("g_power_topology_delegate.SetOutletEndpoint(g_antenna_endpoint_id)", source)
        self.assertIn("topology_config.delegate = &g_power_topology_delegate", source)
        self.assertIn("topology_config.feature_flags = cluster::power_topology::feature::set_topology::get_id()", source)
        self.assertIn("cluster::power_topology::create(meter_endpoint", source)
        self.assertIn("meter_endpoint, endpoint::electrical_sensor::get_device_type_id()", source)
        self.assertNotIn("endpoint::electrical_sensor::add(", source)
        self.assertNotIn("cluster::electrical_power_measurement::create(", source)
        self.assertNotIn("cluster::electrical_energy_measurement::create(", source)
        self.assertNotIn("feature::dynamic_power_flow::", source)
        self.assertIn("smart_meter_start(g_meter_endpoint_id, &g_power_delegate)", source)

    @unittest.skipUnless(shutil.which("c++"), "A C++ compiler is needed")
    def test_real_delegate_lists_only_the_bound_outlet(self):
        # The stub supplies only CHIP's interface/types; the delegate under test
        # is the actual firmware header. A full firmware build checks SDK ABI.
        stub = r'''
#pragma once
#include <cstddef>
#include <cstdint>
using CHIP_ERROR = int;
constexpr CHIP_ERROR CHIP_NO_ERROR = 0;
constexpr CHIP_ERROR CHIP_ERROR_PROVIDER_LIST_EXHAUSTED = 1;
namespace chip {
using EndpointId = uint16_t;
constexpr EndpointId kInvalidEndpointId = 0xffff;
namespace app::Clusters::PowerTopology {
class Delegate {
public:
    virtual ~Delegate() = default;
    virtual CHIP_ERROR GetAvailableEndpointAtIndex(size_t, EndpointId &) = 0;
    virtual CHIP_ERROR GetActiveEndpointAtIndex(size_t, EndpointId &) = 0;
};
}
}
'''
        harness = r'''
#include <cassert>
#include "meter_power_topology.h"
int main() {
    MeterPowerTopologyDelegate delegate;
    chip::EndpointId endpoint = 99;
    assert(delegate.GetAvailableEndpointAtIndex(0, endpoint) == CHIP_ERROR_PROVIDER_LIST_EXHAUSTED);
    assert(endpoint == 99); // No uninitialized endpoint advertised.
    for (chip::EndpointId outlet : {chip::EndpointId{2}, chip::EndpointId{300}}) {
        delegate.SetOutletEndpoint(outlet);
        assert(delegate.GetAvailableEndpointAtIndex(0, endpoint) == CHIP_NO_ERROR);
        assert(endpoint == outlet);
        assert(delegate.GetAvailableEndpointAtIndex(1, endpoint) == CHIP_ERROR_PROVIDER_LIST_EXHAUSTED);
        assert(endpoint == outlet);
        assert(delegate.GetAvailableEndpointAtIndex(size_t(-1), endpoint) == CHIP_ERROR_PROVIDER_LIST_EXHAUSTED);
        // Static topology never pretends OnOff controls household power flow.
        assert(delegate.GetActiveEndpointAtIndex(0, endpoint) == CHIP_ERROR_PROVIDER_LIST_EXHAUSTED);
        assert(delegate.GetActiveEndpointAtIndex(1, endpoint) == CHIP_ERROR_PROVIDER_LIST_EXHAUSTED);
    }
    delegate.SetOutletEndpoint(chip::kInvalidEndpointId);
    assert(delegate.GetAvailableEndpointAtIndex(0, endpoint) == CHIP_ERROR_PROVIDER_LIST_EXHAUSTED);
}
'''
        harness = '#include <initializer_list>\n' + harness
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            include = temp / "app/clusters/power-topology-server/PowerTopologyDelegate.h"
            include.parent.mkdir(parents=True)
            include.write_text(stub)
            test = temp / "topology.cpp"
            test.write_text(harness)
            executable = temp / "topology-test"
            subprocess.run([shutil.which("c++"), "-std=c++17", "-Wall", "-Wextra", "-Werror",
                            "-I", str(temp), "-I", str(ROOT / "firmware/main"),
                            str(test), "-o", str(executable)], check=True)
            subprocess.run([str(executable)], check=True)


if __name__ == "__main__":
    unittest.main()
