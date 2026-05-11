"""Support for Gardena Smart System sensors."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    ATTR_BATTERY_STATE,
    ATTR_RF_LINK_LEVEL,
    ATTR_RF_LINK_STATE,
)
from .coordinator import GardenaSmartSystemCoordinator
from .entities import GardenaEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Gardena Smart System sensors."""
    coordinator: GardenaSmartSystemCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Create sensor entities for each device
    entities = []
    
    for location in coordinator.locations.values():
        for device in location.devices.values():
            _LOGGER.debug(f"Checking device {device.name} ({device.id}) - Services: {list(device.services.keys())}")
            
            # Add battery and RF link sensors for devices that have COMMON service
            if "COMMON" in device.services:
                common_services = device.services["COMMON"]
                _LOGGER.debug(f"Found {len(common_services)} common services for device: {device.name} ({device.id})")
                for common_service in common_services:
                    # Only create battery sensor if device has a battery.
                    # Include when battery_level is present even if battery_state is not yet
                    # populated (soil sensors can return null battery_state at initial load).
                    has_battery = (
                        common_service.battery_state not in [None, "NO_BATTERY"]
                        or common_service.battery_level is not None
                    )
                    if has_battery:
                        _LOGGER.debug(f"Creating battery sensor for device with battery: {device.name} (battery_state: {common_service.battery_state})")
                        entities.append(GardenaBatterySensor(coordinator, device, common_service))
                    else:
                        _LOGGER.debug(f"Skipping battery sensor for device without battery: {device.name} (battery_state: {common_service.battery_state})")

                    # RF Link Quality sensor
                    if common_service.rf_link_level is not None:
                        entities.append(GardenaRFLinkLevelSensor(coordinator, device, common_service))
            
            # Add mower sensors
            if "MOWER" in device.services:
                mower_services = device.services["MOWER"]
                for mower_service in mower_services:
                    entities.append(GardenaMowerErrorSensor(coordinator, device, mower_service))
                    if mower_service.operating_hours is not None:
                        entities.append(GardenaMowerOperatingHoursSensor(coordinator, device, mower_service))

            # Add watering end time sensors for valves
            if "VALVE" in device.services:
                valve_services = device.services["VALVE"]
                for valve_service in valve_services:
                    entities.append(GardenaValveRemainingTimeSensor(coordinator, device, valve_service))

            # Add sensor entities if available
            if "SENSOR" in device.services:
                sensor_services = device.services["SENSOR"]
                _LOGGER.debug(f"Found {len(sensor_services)} sensor services for device: {device.name} ({device.id})")
                for sensor_service in sensor_services:
                    _LOGGER.debug(f"Creating sensor entities for service: {sensor_service.id}")
                    
                    # Check if this is a soil sensor (has soil_humidity or soil_temperature)
                    is_soil_sensor = (sensor_service.soil_humidity is not None or 
                                    sensor_service.soil_temperature is not None)
                    
                    # Create temperature sensors
                    if sensor_service.soil_temperature is not None:
                        entities.append(GardenaTemperatureSensor(coordinator, device, sensor_service, "soil_temperature", is_soil_sensor))
                    if sensor_service.ambient_temperature is not None:
                        entities.append(GardenaTemperatureSensor(coordinator, device, sensor_service, "ambient_temperature", is_soil_sensor))
                    
                    # Create humidity sensor (only for soil sensors)
                    if sensor_service.soil_humidity is not None:
                        entities.append(GardenaHumiditySensor(coordinator, device, sensor_service))
                    
                    # Create light sensor
                    if sensor_service.light_intensity is not None:
                        entities.append(GardenaLightSensor(coordinator, device, sensor_service))

    # Add WebSocket status sensor
    entities.append(GardenaWebSocketStatusSensor(coordinator, entry.entry_id))

    _LOGGER.debug(f"Created {len(entities)} sensor entities")
    async_add_entities(entities)


class GardenaBatterySensor(GardenaEntity, SensorEntity):
    """Representation of a Gardena battery sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: GardenaSmartSystemCoordinator, device, common_service) -> None:
        """Initialize the battery sensor."""
        super().__init__(coordinator, device, "COMMON")
        self._common_service = common_service
        self._device_id = device.id
        self._attr_name = f"{device.name} Battery Level"
        self._attr_unique_id = f"{device.id}_{common_service.id}_battery_level"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_icon = "mdi:battery"

    def _get_current_common_service(self):
        """Get current common service from coordinator (fresh data)."""
        device = self.coordinator.get_device_by_id(self._device_id)
        if device and "COMMON" in device.services:
            for service in device.services["COMMON"]:
                if service.id == self._common_service.id:
                    return service
        return None

    @property
    def native_value(self) -> int | None:
        """Return the battery level."""
        current_service = self._get_current_common_service()
        return current_service.battery_level if current_service else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        attrs = super().extra_state_attributes
        current_service = self._get_current_common_service()
        if current_service:
            attrs.update({
                ATTR_BATTERY_STATE: current_service.battery_state,
                ATTR_RF_LINK_LEVEL: current_service.rf_link_level,
                ATTR_RF_LINK_STATE: current_service.rf_link_state,
            })
        return attrs


class GardenaMowerErrorSensor(GardenaEntity, SensorEntity):
    """Representation of a Gardena mower error code sensor."""

    _attr_translation_key = "mower_error"
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.ENUM

    def __init__(self, coordinator: GardenaSmartSystemCoordinator, device, mower_service) -> None:
        """Initialize the mower error sensor."""
        super().__init__(coordinator, device, "MOWER")
        self._mower_service = mower_service
        self._device_id = device.id
        self._attr_name = None
        self._attr_unique_id = f"{device.id}_{mower_service.id}_last_error_code"
        self._attr_icon = "mdi:alert-circle-outline"
        self._attr_options = [
            "no_message", "outside_working_area", "no_loop_signal",
            "wrong_loop_signal", "loop_sensor_problem_front", "loop_sensor_problem_rear",
            "trapped", "upside_down", "low_battery", "empty_battery", "no_drive",
            "lifted", "stuck_in_charging_station", "charging_station_blocked",
            "collision_sensor_problem_rear", "collision_sensor_problem_front",
            "wheel_motor_blocked_right", "wheel_motor_blocked_left",
            "cutting_system_blocked", "steep_slope", "parked_daily_limit_reached",
            "unknown",
        ]

    def _get_current_mower_service(self):
        """Get current mower service from coordinator (fresh data)."""
        device = self.coordinator.get_device_by_id(self._device_id)
        if device and "MOWER" in device.services:
            for service in device.services["MOWER"]:
                if service.id == self._mower_service.id:
                    return service
        return None

    @property
    def native_value(self) -> str | None:
        """Return the last error code."""
        current_service = self._get_current_mower_service()
        if not current_service:
            return None
        error_code = current_service.last_error_code
        if error_code:
            return error_code.lower()
        return None

    @property
    def icon(self) -> str:
        """Return icon based on error state."""
        value = self.native_value
        if value and value != "no_message":
            return "mdi:alert-circle"
        return "mdi:check-circle-outline"


class GardenaMowerOperatingHoursSensor(GardenaEntity, SensorEntity):
    """Representation of a Gardena mower operating hours sensor."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_device_class = SensorDeviceClass.DURATION

    def __init__(self, coordinator: GardenaSmartSystemCoordinator, device, mower_service) -> None:
        """Initialize the operating hours sensor."""
        super().__init__(coordinator, device, "MOWER")
        self._mower_service = mower_service
        self._device_id = device.id
        self._attr_name = f"{device.name} Operating Hours"
        self._attr_unique_id = f"{device.id}_{mower_service.id}_operating_hours"
        self._attr_native_unit_of_measurement = UnitOfTime.HOURS
        self._attr_icon = "mdi:clock-outline"

    def _get_current_mower_service(self):
        """Get current mower service from coordinator (fresh data)."""
        device = self.coordinator.get_device_by_id(self._device_id)
        if device and "MOWER" in device.services:
            for service in device.services["MOWER"]:
                if service.id == self._mower_service.id:
                    return service
        return None

    @property
    def native_value(self) -> int | None:
        """Return the operating hours."""
        current_service = self._get_current_mower_service()
        return current_service.operating_hours if current_service else None


class GardenaRFLinkLevelSensor(GardenaEntity, SensorEntity):
    """Representation of a Gardena RF link quality sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: GardenaSmartSystemCoordinator, device, common_service) -> None:
        """Initialize the RF link level sensor."""
        super().__init__(coordinator, device, "COMMON")
        self._common_service = common_service
        self._device_id = device.id
        self._attr_name = f"{device.name} RF Link Quality"
        self._attr_unique_id = f"{device.id}_{common_service.id}_rf_link_level"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_icon = "mdi:signal"

    def _get_current_common_service(self):
        """Get current common service from coordinator (fresh data)."""
        device = self.coordinator.get_device_by_id(self._device_id)
        if device and "COMMON" in device.services:
            for service in device.services["COMMON"]:
                if service.id == self._common_service.id:
                    return service
        return None

    @property
    def native_value(self) -> int | None:
        """Return the RF link level."""
        current_service = self._get_current_common_service()
        return current_service.rf_link_level if current_service else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        attrs = super().extra_state_attributes
        current_service = self._get_current_common_service()
        if current_service:
            attrs[ATTR_RF_LINK_STATE] = current_service.rf_link_state
        return attrs


class GardenaTemperatureSensor(GardenaEntity, SensorEntity):
    """Representation of a Gardena temperature sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: GardenaSmartSystemCoordinator, device, sensor_service, temp_attr: str, is_soil_sensor: bool = False) -> None:
        """Initialize the temperature sensor."""
        super().__init__(coordinator, device, "SENSOR")
        self._sensor_service = sensor_service
        self._device_id = device.id
        self._temp_attr = temp_attr
        
        if temp_attr == "soil_temperature":
            self._attr_name = f"{device.name} Soil Temperature"
            self._attr_unique_id = f"{device.id}_{sensor_service.id}_soil_temperature"
        else:
            self._attr_name = f"{device.name} Ambient Temperature"
            self._attr_unique_id = f"{device.id}_{sensor_service.id}_ambient_temperature"
        
        # Add soil sensor indicator to name if it's a soil sensor
        if is_soil_sensor and temp_attr == "soil_temperature":
            self._attr_name = f"{device.name} Soil Temperature (Soil Sensor)"
        
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_icon = "mdi:thermometer"

    def _get_current_sensor_service(self):
        """Get current sensor service from coordinator (fresh data)."""
        device = self.coordinator.get_device_by_id(self._device_id)
        if device and "SENSOR" in device.services:
            for service in device.services["SENSOR"]:
                if service.id == self._sensor_service.id:
                    return service
        return None

    @property
    def native_value(self) -> int | None:
        """Return the temperature value."""
        current_service = self._get_current_sensor_service()
        if not current_service:
            return None
            
        if self._temp_attr == "soil_temperature":
            return current_service.soil_temperature
        else:
            return current_service.ambient_temperature


class GardenaHumiditySensor(GardenaEntity, SensorEntity):
    """Representation of a Gardena humidity sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: GardenaSmartSystemCoordinator, device, sensor_service) -> None:
        """Initialize the humidity sensor."""
        super().__init__(coordinator, device, "SENSOR")
        self._sensor_service = sensor_service
        self._device_id = device.id
        self._attr_name = f"{device.name} Soil Humidity"
        self._attr_unique_id = f"{device.id}_{sensor_service.id}_soil_humidity"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_device_class = SensorDeviceClass.MOISTURE
        self._attr_icon = "mdi:water-percent"

    def _get_current_sensor_service(self):
        """Get current sensor service from coordinator (fresh data)."""
        device = self.coordinator.get_device_by_id(self._device_id)
        if device and "SENSOR" in device.services:
            for service in device.services["SENSOR"]:
                if service.id == self._sensor_service.id:
                    return service
        return None

    @property
    def native_value(self) -> int | None:
        """Return the humidity value."""
        current_service = self._get_current_sensor_service()
        return current_service.soil_humidity if current_service else None


class GardenaLightSensor(GardenaEntity, SensorEntity):
    """Representation of a Gardena light sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: GardenaSmartSystemCoordinator, device, sensor_service) -> None:
        """Initialize the light sensor."""
        super().__init__(coordinator, device, "SENSOR")
        self._sensor_service = sensor_service
        self._device_id = device.id
        self._attr_name = f"{device.name} Light Intensity"
        self._attr_unique_id = f"{device.id}_{sensor_service.id}_light_intensity"
        self._attr_native_unit_of_measurement = "lux"
        self._attr_device_class = SensorDeviceClass.ILLUMINANCE
        self._attr_icon = "mdi:white-balance-sunny"

    def _get_current_sensor_service(self):
        """Get current sensor service from coordinator (fresh data)."""
        device = self.coordinator.get_device_by_id(self._device_id)
        if device and "SENSOR" in device.services:
            for service in device.services["SENSOR"]:
                if service.id == self._sensor_service.id:
                    return service
        return None

    @property
    def native_value(self) -> int | None:
        """Return the light intensity value."""
        current_service = self._get_current_sensor_service()
        return current_service.light_intensity if current_service else None


class GardenaValveRemainingTimeSensor(GardenaEntity, SensorEntity):
    """Sensor that shows the watering end time for a valve."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: GardenaSmartSystemCoordinator, device, valve_service) -> None:
        """Initialize the valve remaining time sensor."""
        super().__init__(coordinator, device, "VALVE")
        self._valve_service = valve_service
        self._device_id = device.id
        valve_name = valve_service.name or device.name
        self._attr_name = f"{valve_name} Watering End"
        self._attr_unique_id = f"{device.id}_{valve_service.id}_watering_end"
        self._attr_icon = "mdi:timer-sand"

    def _get_current_valve_service(self):
        """Get current valve service from coordinator (fresh data)."""
        device = self.coordinator.get_device_by_id(self._device_id)
        if device and "VALVE" in device.services:
            for service in device.services["VALVE"]:
                if service.id == self._valve_service.id:
                    return service
        return None

    @property
    def native_value(self) -> datetime | None:
        """Return the watering end timestamp."""
        current_service = self._get_current_valve_service()
        if not current_service:
            return None

        if current_service.activity in ("MANUAL_WATERING", "SCHEDULED_WATERING"):
            if current_service.duration and current_service.duration_timestamp:
                try:
                    start = datetime.fromisoformat(
                        current_service.duration_timestamp.replace("Z", "+00:00")
                    )
                    return start + timedelta(seconds=current_service.duration)
                except (ValueError, TypeError):
                    return None
        return None


class GardenaWebSocketStatusSensor(GardenaEntity, SensorEntity):
    """Representation of a Gardena WebSocket status sensor."""

    def __init__(self, coordinator: GardenaSmartSystemCoordinator, entry_id: str) -> None:
        """Initialize the WebSocket status sensor."""
        # Create a dummy device for the base entity
        from .models import GardenaDevice
        dummy_device = GardenaDevice(
            id=f"websocket_status_{entry_id}",
            name="WebSocket Status",
            model_type="WebSocket Client",
            serial="websocket",
            services={},
            location_id=""
        )

        super().__init__(coordinator, dummy_device, "WEBSOCKET")
        self._attr_name = "Gardena WebSocket Status"
        self._attr_unique_id = f"gardena_websocket_status_{entry_id}"
        self._attr_icon = "mdi:connection"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # WebSocket status sensor is always available
        return True

    @property
    def native_value(self) -> str:
        """Return the WebSocket connection status."""
        if self.coordinator.websocket_client:
            status = self.coordinator.websocket_client.connection_status
            _LOGGER.debug(f"WebSocket status sensor: client available, status={status}")
            return status
        _LOGGER.debug("WebSocket status sensor: client not available")
        return "disconnected"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        attrs = super().extra_state_attributes
        
        # Add reconnect button when disconnected
        if self.native_value == "disconnected":
            attrs["reconnect_button"] = True
            attrs["reconnect_service"] = "gardena_smart_system.reconnect_websocket"
        
        if self.coordinator.websocket_client:
            attrs.update({
                "reconnect_attempts": self.coordinator.websocket_client.reconnect_attempts,
                "is_connected": self.coordinator.websocket_client.is_connected,
                "is_connecting": self.coordinator.websocket_client.is_connecting,
            })
        
        return attrs
