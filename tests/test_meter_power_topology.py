"""Guard independent household metering against outlet-consumption regressions."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MeterPowerTopologyTests(unittest.TestCase):
    def test_independent_meter_and_antenna_preserve_existing_paths(self):
        source = (ROOT / "firmware/main/app_main.cpp").read_text()
        # The same two endpoint IDs retain HA readings, PIN and RF control.
        self.assertEqual(source.count("endpoint::electrical_meter::create("), 1)
        self.assertEqual(source.count("endpoint::on_off_plug_in_unit::create("), 1)
        self.assertLess(source.index("endpoint::electrical_meter::create("),
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
        # A utility sensor/NodeTopology or SetTopology would attach whole-house
        # readings to the controllable outlet again.
        self.assertNotIn("endpoint::electrical_sensor::", source)
        self.assertNotIn("cluster::power_topology::", source)
        self.assertNotIn("g_power_topology_delegate", source)
        # The meter helper owns the only EPM/EEM instances.
        self.assertNotIn("cluster::electrical_power_measurement::create(", source)
        self.assertNotIn("cluster::electrical_energy_measurement::create(", source)
        antenna = source[source.index("endpoint::on_off_plug_in_unit::config_t"):
                         source.index("cluster::keypad_input::config_t")]
        self.assertNotIn("electrical_power_measurement", antenna)
        self.assertNotIn("electrical_energy_measurement", antenna)


if __name__ == "__main__":
    unittest.main()
