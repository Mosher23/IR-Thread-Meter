idf_component_register(
    SRCS
        "app_main.cpp"
        "board_config.cpp"
        "electrical_meter_delegate.cpp"
        "meter_pin_delegate.cpp"
        "smart_meter.cpp"
        "sml.cpp"
    INCLUDE_DIRS "."
    PRIV_INCLUDE_DIRS "${ESP_MATTER_PATH}/examples/common/utils"
    PRIV_REQUIRES console driver nvs_flash esp_matter chip app_update
)

target_compile_options(${COMPONENT_LIB} PRIVATE "-DCHIP_HAVE_CONFIG_H")
