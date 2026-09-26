#pragma once

#include <esp_err.h>

// Saved separately from Matter fabrics; survives a normal Matter factory reset.
bool board_config_init();
esp_err_t board_config_set_antenna(bool external);
