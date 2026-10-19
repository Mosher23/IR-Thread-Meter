"""Check the actual topology delegate and keep metering on its existing endpoint."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MeterPowerTopologyTests(unittest.TestCase):
    def test_single_application_outlet_and_whole_device_sensor_preserve_paths(self):
        source = (ROOT / "firmware/main/app_main.cpp").read_text()
        # Endpoint 1 retains all existing HA measurement and PIN paths.
        self.assertEqual(source.count("endpoint::electrical_sensor::create("), 1)
        self.assertNotIn("endpoint::electrical_meter::", source)
        self.assertEqual(source.count("endpoint::on_off_plug_in_unit::create("), 1)
        self.assertLess(source.index("endpoint::electrical_sensor::create("),
                        source.index("endpoint::on_off_plug_in_unit::create("))
        self.assertIn("meter_config.with_electrical_power_measurement()", source)
        self.assertIn("meter_config.with_electrical_energy_measurement()", source)
        self.assertIn("power_config.delegate = &g_power_delegate", source)
        self.assertIn("meter_config.power_topology.delegate = &g_power_topology_delegate", source)
        self.assertIn("cluster::power_topology::feature::node_topology::get_id()", source)
        self.assertNotIn("feature::set_topology::", source)
        self.assertNotIn("feature::dynamic_power_flow::", source)
        # The sensor helper creates exactly one of each measurement cluster.
        self.assertNotIn("cluster::electrical_power_measurement::create(", source)
        self.assertNotIn("cluster::electrical_energy_measurement::create(", source)
        self.assertNotIn("cluster::power_topology::create(", source)
        self.assertIn("smart_meter_start(g_meter_endpoint_id, &g_power_delegate)", source)
        self.assertIn("cluster::keypad_input::create(\n        meter_endpoint", source)

    @unittest.skipUnless(shutil.which("c++"), "A C++ compiler is needed")
    def test_whole_device_delegate_never_exposes_endpoint_lists(self):
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
    for (size_t index : {size_t{0}, size_t{1}, size_t(-1)}) {
        assert(delegate.GetAvailableEndpointAtIndex(index, endpoint) == CHIP_ERROR_PROVIDER_LIST_EXHAUSTED);
        assert(endpoint == 99);
        assert(delegate.GetActiveEndpointAtIndex(index, endpoint) == CHIP_ERROR_PROVIDER_LIST_EXHAUSTED);
        assert(endpoint == 99);
    }
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
