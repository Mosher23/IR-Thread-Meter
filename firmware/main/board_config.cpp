#include "board_config.h"
#include <esp_err.h>
#include <esp_log.h>
#include <nvs.h>
#include <nvs_flash.h>
#include <cstdlib>

bool board_config_init()
{
    // Never auto-erase: a lost antenna setting can strand an installed meter.
    ESP_ERROR_CHECK(nvs_flash_init_partition("board_cfg"));
    nvs_handle_t handle;
    ESP_ERROR_CHECK(nvs_open_from_partition("board_cfg", "board", NVS_READWRITE, &handle));
    uint8_t antenna = 0;
    esp_err_t err = nvs_get_u8(handle, "antenna", &antenna);
    if (err == ESP_ERR_NVS_NOT_FOUND) {
#if CONFIG_SMARTMETER_REQUIRE_BOARD_CONFIG
        ESP_LOGE("board_config", "Missing antenna setting: install a USB bootstrap build first");
        abort();
#else
#if CONFIG_SMARTMETER_EXTERNAL_ANTENNA
        antenna = 1;
#endif
        ESP_ERROR_CHECK(nvs_set_u8(handle, "antenna", antenna));
        ESP_ERROR_CHECK(nvs_commit(handle));
#endif
    } else {
        ESP_ERROR_CHECK(err);
    }
    nvs_close(handle);
    if (antenna > 1) {
        ESP_LOGE("board_config", "Invalid saved antenna setting");
        abort();
    }
    return antenna == 1;
}

esp_err_t board_config_set_antenna(bool external)
{
    nvs_handle_t handle;
    esp_err_t error = nvs_open_from_partition("board_cfg", "board", NVS_READWRITE, &handle);
    if (error != ESP_OK) {
        return error;
    }
    error = nvs_set_u8(handle, "antenna", external ? 1 : 0);
    if (error == ESP_OK) {
        error = nvs_commit(handle);
    }
    nvs_close(handle);
    return error;
}
