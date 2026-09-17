"""Offline contract tests for the HA companion's power and PIN UI."""

import asyncio
import importlib.util
from pathlib import Path
import sys
from time import monotonic
import types
import unittest
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1] / "custom_components/smartmeter_pin"


def module(name, **members):
    result = types.ModuleType(name)
    result.__dict__.update(members)
    return result


class FakeEntity:
    def async_write_ha_state(self):
        pass

    async def async_added_to_hass(self):
        pass

    async def async_will_remove_from_hass(self):
        pass


class FakeCoordinator:
    def __class_getitem__(cls, _item):
        return cls

    def __init__(self, _hass, _logger, *, name, update_interval):
        self.name = name
        self.update_interval = update_interval
        self.data = None


class FakeCoordinatorEntity:
    def __init__(self, coordinator):
        self.coordinator = coordinator


class HAError(Exception):
    pass


class SendKey:
    def __init__(self, *, keyCode):
        self.keyCode = keyCode


package = module("companion_test", __path__=[str(ROOT)], SmartMeterRuntimeData=object)
stubs = {
    "companion_test": package,
    "matter_server.common.helpers.util": module(
        "util", create_attribute_path=lambda endpoint, cluster, attribute: f"{endpoint}/{cluster}/{attribute}"
    ),
    "matter_server.common.models": module(
        "models", EventType=types.SimpleNamespace(NODE_UPDATED=1)
    ),
    "chip.clusters": module(
        "clusters", Objects=types.SimpleNamespace(
            KeypadInput=types.SimpleNamespace(Commands=types.SimpleNamespace(SendKey=SendKey))
        )
    ),
    "homeassistant.components.binary_sensor": module("binary_sensor", BinarySensorEntity=FakeEntity),
    "homeassistant.components.button": module("button", ButtonEntity=FakeEntity),
    "homeassistant.components.sensor": module(
        "sensor", SensorEntity=FakeEntity,
        SensorDeviceClass=types.SimpleNamespace(POWER="power"),
        SensorStateClass=types.SimpleNamespace(MEASUREMENT="measurement"),
    ),
    "homeassistant.components.text": module(
        "text", TextEntity=FakeEntity, TextMode=types.SimpleNamespace(PASSWORD="password")
    ),
    "homeassistant.config_entries": module("config_entries", ConfigEntry=object),
    "homeassistant.const": module(
        "const", EntityCategory=types.SimpleNamespace(CONFIG="config", DIAGNOSTIC="diagnostic"),
        UnitOfPower=types.SimpleNamespace(WATT="W"),
    ),
    "homeassistant.core": module("core", HomeAssistant=object, callback=lambda fn: fn),
    "homeassistant.exceptions": module("exceptions", HomeAssistantError=HAError),
    "homeassistant.helpers.entity_platform": module(
        "entity_platform", AddEntitiesCallback=object
    ),
    "homeassistant.helpers.update_coordinator": module(
        "update_coordinator", DataUpdateCoordinator=FakeCoordinator,
        CoordinatorEntity=FakeCoordinatorEntity, UpdateFailed=HAError,
    ),
}


def load(name):
    spec = importlib.util.spec_from_file_location(f"companion_test.{name}", ROOT / f"{name}.py")
    result = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = result
    spec.loader.exec_module(result)
    return result


with patch.dict(sys.modules, stubs):
    load("const")
    coordinator = load("coordinator")
    sensor = load("sensor")
    text = load("text")
    button = load("button")


class Runtime:
    def __init__(self, client, meter_coordinator):
        self.matter_client = client
        self.coordinator = meter_coordinator
        self.node_id = 5
        self.endpoint_id = 1
        self.device_id = "meter-device"
        self.pending_pin = None
        self.pin_expires_at = 0
        self.clear_pin_display = None
        self.pin_send_lock = asyncio.Lock()

    def stage_pin(self, pin):
        self.pending_pin = pin
        self.pin_expires_at = monotonic() + 120

    def take_pin(self):
        pin = self.pending_pin if monotonic() < self.pin_expires_at else None
        self.pending_pin = None
        if self.clear_pin_display:
            self.clear_pin_display()
        return pin


class CompanionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.node = types.SimpleNamespace(available=True)
        self.client = types.SimpleNamespace(
            get_node=lambda _: self.node,
            read_attribute=AsyncMock(),
            send_device_command=AsyncMock(),
        )
        self.coordinator = coordinator.SmartMeterCoordinator(None, self.client, 5, 1)
        self.runtime = Runtime(self.client, self.coordinator)

    async def test_one_poll_reads_power_and_all_diagnostics(self):
        self.client.read_attribute.return_value = {"1/144/8": 524000}
        data = await self.coordinator._async_update_data()
        self.assertEqual(data["1/144/8"], 524000)
        paths = self.client.read_attribute.await_args.args[1]
        self.assertEqual(len(paths), 6)
        self.assertIn("1/144/8", paths)
        self.assertIn("0/40/9", paths)
        self.assertIn("0/40/10", paths)
        self.assertEqual(self.coordinator.update_interval.total_seconds(), 30)

    async def test_power_is_watts_and_null_is_unknown(self):
        entity = sensor.MeterActivePowerSensor(self.runtime)
        self.coordinator.data = {"1/144/8": 524000}
        self.assertEqual(entity.native_value, 524)
        self.coordinator.data = {"1/144/8": None}
        self.assertIsNone(entity.native_value)

    async def test_pin_requires_explicit_button_and_never_enters_state(self):
        field = text.MeterPinTextEntity(self.runtime)
        send = button.SendMeterPinButton(self.runtime)
        await field.async_set_value("1234")
        self.assertEqual(field._attr_native_value, "••••")
        self.client.send_device_command.assert_not_awaited()
        await send.async_press()
        codes = [call.kwargs["command"].keyCode for call in self.client.send_device_command.await_args_list]
        self.assertEqual(codes, [0x2C, 0x21, 0x22, 0x23, 0x24, 0x00])
        self.assertEqual(field._attr_native_value, "")
        self.assertIsNone(self.runtime.pending_pin)

    async def test_button_without_pin_does_not_send(self):
        send = button.SendMeterPinButton(self.runtime)
        with self.assertRaisesRegex(HAError, "Enter a four-digit PIN"):
            await send.async_press()
        self.client.send_device_command.assert_not_awaited()

    async def test_offline_meter_does_not_expose_stale_values(self):
        self.node.available = False
        with self.assertRaisesRegex(HAError, "offline"):
            await self.coordinator._async_update_data()
        self.client.read_attribute.assert_not_awaited()
