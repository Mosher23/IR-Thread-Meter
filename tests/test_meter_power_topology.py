"""Guard independent household metering against outlet-consumption regressions."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MeterPowerTopologyTests(unittest.TestCase):
    def test_independent_meter_and_antenna_preserve_existing_paths(self):
        source = (ROOT / "firmware/main/app_main.cpp").read_text()
        # The same two endpoint IDs retain HA readings, PIN and RF control.
        self.assertEqual(source.count("endpoint::electrical_sensor::create("), 1)
        self.assertEqual(source.count("endpoint::on_off_plug_in_unit::create("), 1)
        self.assertLess(source.index("endpoint::electrical_sensor::create("),
                        source.index("endpoint::on_off_plug_in_unit::create("))
        self.assertIn("meter_config.electrical_power_measurement.delegate = &g_power_delegate", source)
        self.assertIn("meter_config.electrical_energy_measurement.feature_flags", source)
        self.assertIn("feature::imported_energy::get_id()", source)
        self.assertIn("feature::exported_energy::get_id()", source)
        self.assertIn("feature::cumulative_energy::get_id()", source)
        self.assertIn("smart_meter_start(g_meter_endpoint_id, &g_power_delegate)", source)
        self.assertIn("cluster::keypad_input::create(" + chr(10) + "        meter_endpoint", source)

    def test_household_readings_are_never_associated_with_antenna_outlet(self):
        source = (ROOT / "firmware/main/app_main.cpp").read_text()
        # The candidate advertises only the measurement type. TreeTopology
        # scopes it to the meter; the RF control remains a sibling.
        self.assertNotIn("endpoint::electrical_meter::", source)
        self.assertIn("meter_config.with_electrical_power_measurement()", source)
        self.assertIn("meter_config.with_electrical_energy_measurement()", source)
        self.assertIn("cluster::power_topology::feature::tree_topology::get_id()", source)
        self.assertIn("meter_config.power_topology.delegate = &g_power_topology_delegate", source)
        self.assertNotIn("cluster::power_topology::create(", source)
        self.assertNotIn("feature::node_topology::", source)
        self.assertNotIn("feature::set_topology::", source)
        self.assertNotIn("feature::dynamic_power_flow::", source)
        self.assertNotIn("endpoint::set_parent_endpoint(", source)
        # The sensor helper owns the only EPM/EEM instances.
        self.assertEqual(source.count("endpoint::electrical_sensor::create("), 1)
        self.assertNotIn("endpoint::electrical_sensor::add(", source)
        self.assertNotIn("cluster::electrical_power_measurement::create(", source)
        self.assertNotIn("cluster::electrical_energy_measurement::create(", source)
        antenna = source[source.index("endpoint::on_off_plug_in_unit::config_t"):
                         source.index("cluster::keypad_input::config_t")]
        self.assertNotIn("electrical_power_measurement", antenna)
        self.assertNotIn("electrical_energy_measurement", antenna)


if __name__ == "__main__":
    unittest.main()
