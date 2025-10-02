#pragma once

/**
 * @file Timing.h
 * @brief Simple cooperative task scheduling helpers
 * 
 * Provides clean timing abstractions to replace ad-hoc millis() checks
 * while maintaining identical timing behavior. No overhead - just readability.
 */

#include <Arduino.h>

/**
 * @brief Simple interval timer helper
 * 
 * Usage: 
 *   static Every oledUpdate(50);  // 20Hz
 *   if (oledUpdate.check()) { ... }
 */
class Every {
public:
    explicit constexpr Every(unsigned long intervalMs) 
        : m_intervalMs(intervalMs), m_lastMs(0) {}
    
    /**
     * @brief Check if interval has elapsed, auto-reset if true
     * @return true if interval elapsed since last check
     */
    bool check() {
        unsigned long now = millis();
        if (now - m_lastMs >= m_intervalMs) {
            m_lastMs = now;
            return true;
        }
        return false;
    }
    
    /**
     * @brief Reset timer (useful for synchronization)
     */
    void reset() {
        m_lastMs = millis();
    }
    
private:
    const unsigned long m_intervalMs;
    unsigned long m_lastMs;
};

/**
 * @brief Age calculation helper (replacement for manual millis() - lastTime)
 * 
 * Usage:
 *   unsigned long age = Age::since(g_lastTelemUpdateMs);
 *   if (age > TELEM_TIMEOUT_MS) { ... }
 */
namespace Age {
    /**
     * @brief Calculate time since given timestamp
     * @param timestampMs Previous timestamp from millis()
     * @return Age in milliseconds
     */
    inline unsigned long since(unsigned long timestampMs) {
        return millis() - timestampMs;
    }
}

/**
 * @brief Flash message timer (for OLED warnings)
 * 
 * Usage:
 *   static FlashTimer horizFlash(700);  // 700ms flash
 *   if (condition) horizFlash.start();
 *   if (horizFlash.isActive()) { show_warning(); }
 */
class FlashTimer {
public:
    explicit constexpr FlashTimer(unsigned long durationMs)
        : m_durationMs(durationMs), m_startMs(0), m_active(false) {}
    
    /**
     * @brief Start flash timer
     */
    void start() {
        m_startMs = millis();
        m_active = true;
    }
    
    /**
     * @brief Check if flash is currently active, auto-expire
     * @return true if flash should be shown
     */
    bool isActive() {
        if (!m_active) return false;
        
        if (millis() - m_startMs > m_durationMs) {
            m_active = false;
        }
        return m_active;
    }
    
    /**
     * @brief Force stop flash
     */
    void stop() {
        m_active = false;
    }
    
private:
    const unsigned long m_durationMs;
    unsigned long m_startMs;
    bool m_active;
};