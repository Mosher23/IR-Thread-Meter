#pragma once

#include <cstdint>

// Antenna holds act on release so a longer reset hold never toggles first.
// Unsigned elapsed time also handles the millisecond counter wrapping.
class BootButtonGestures {
public:
    enum class Action { None, ToggleAntenna, FactoryReset };
    static constexpr uint32_t kDebounceMs = 50;
    static constexpr uint32_t kShortPressMs = 700;
    static constexpr uint32_t kTapGapMs = 2000;
    static constexpr uint32_t kAntennaHoldMs = 3000;
    static constexpr uint32_t kResetHoldMs = 10000;

    Action Update(bool pressed, uint32_t now_ms)
    {
        if (pressed) {
            if (!m_pressed) {
                m_pressed = true;
                m_pressed_at = now_ms;
            }
            if (!m_consumed && now_ms - m_pressed_at >= kResetHoldMs) {
                m_consumed = true;
                m_taps = 0;
                return Action::FactoryReset;
            }
            return Action::None;
        }
        if (!m_pressed) {
            if (m_taps != 0 && now_ms - m_last_tap > kTapGapMs) {
                m_taps = 0;
            }
            return Action::None;
        }
        m_pressed = false;
        const uint32_t held_ms = now_ms - m_pressed_at;
        if (m_consumed) {
            m_consumed = false;
            return Action::None;
        }
        if (held_ms >= kResetHoldMs) {
            m_taps = 0;
            return Action::FactoryReset;
        }
        if (held_ms >= kAntennaHoldMs) {
            m_taps = 0;
            return Action::ToggleAntenna;
        }
        if (held_ms > kShortPressMs) {
            m_taps = 0;
            return Action::None;
        }
        if (held_ms < kDebounceMs) {
            return Action::None;
        }
        if (m_taps != 0 && now_ms - m_last_tap > kTapGapMs) {
            m_taps = 0;
        }
        m_last_tap = now_ms;
        if (++m_taps == 3) {
            m_taps = 0;
            return Action::ToggleAntenna;
        }
        return Action::None;
    }

private:
    bool m_pressed = false;
    bool m_consumed = false;
    uint32_t m_pressed_at = 0;
    uint32_t m_last_tap = 0;
    unsigned m_taps = 0;
};
