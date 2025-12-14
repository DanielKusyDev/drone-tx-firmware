#pragma once
#include <Arduino.h>

/**
 * @file logger.h
 * @brief Professional logging system for transmitter firmware
 *
 * Provides hierarchical log levels, category-based filtering, and
 * runtime configuration via serial commands. Designed to match the
 * drone receiver's logging architecture for consistency.
 */

// ============================================================================
// Log Levels
// ============================================================================

enum class LogLevel : uint8_t {
    NONE  = 0,  // No logging
    ERROR = 1,  // Critical errors only
    WARN  = 2,  // Warnings and errors
    INFO  = 3,  // General information (default)
    DEBUG = 4,  // Detailed debugging
    TRACE = 5   // Very verbose tracing
};

// ============================================================================
// Log Categories (Bitmask)
// ============================================================================

enum class LogCategory : uint32_t {
    SYSTEM   = 0x00000001,  // System initialization and core functionality
    INPUTS   = 0x00000002,  // RC input processing (joysticks, switches)
    RADIO    = 0x00000004,  // Radio/ESP-NOW communication
    OLED     = 0x00000008,  // OLED display updates
    BATTERY  = 0x00000010,  // Battery monitoring
    TELEM    = 0x00000020,  // Telemetry reception and processing
    CONFIG   = 0x00000040,  // Configuration management
    UI       = 0x00000080,  // User interface / button handling
    CALIB    = 0x00000100,  // Calibration system
    ALL      = 0xFFFFFFFF   // All categories
};

// Bitwise operators for LogCategory
inline LogCategory operator|(LogCategory a, LogCategory b) {
    return static_cast<LogCategory>(static_cast<uint32_t>(a) | static_cast<uint32_t>(b));
}

inline LogCategory operator&(LogCategory a, LogCategory b) {
    return static_cast<LogCategory>(static_cast<uint32_t>(a) & static_cast<uint32_t>(b));
}

inline LogCategory operator~(LogCategory a) {
    return static_cast<LogCategory>(~static_cast<uint32_t>(a));
}

inline LogCategory& operator|=(LogCategory& a, LogCategory b) {
    a = a | b;
    return a;
}

inline LogCategory& operator&=(LogCategory& a, LogCategory b) {
    a = a & b;
    return a;
}

// ============================================================================
// Configuration Structure
// ============================================================================

struct LogConfig {
    LogLevel global_level = LogLevel::INFO;
    LogCategory enabled_categories = LogCategory::SYSTEM | LogCategory::BATTERY;
    bool show_timestamp = false;
    bool show_category = true;
    bool show_level = false;
};

// ============================================================================
// Logger Class
// ============================================================================

class Logger {
public:
    /**
     * @brief Initialize the logger system
     * Sets up serial and prints initial info
     */
    static void init();

    /**
     * @brief Set the global log level
     * @param level The minimum severity level to log
     */
    static void setLevel(LogLevel level);

    /**
     * @brief Enable a specific category
     * @param cat The category to enable
     */
    static void enableCategory(LogCategory cat);

    /**
     * @brief Disable a specific category
     * @param cat The category to disable
     */
    static void disableCategory(LogCategory cat);

    /**
     * @brief Enable all categories
     */
    static void enableAllCategories();

    /**
     * @brief Log an error message (level ERROR)
     */
    static void error(LogCategory cat, const char* fmt, ...);

    /**
     * @brief Log a warning message (level WARN)
     */
    static void warn(LogCategory cat, const char* fmt, ...);

    /**
     * @brief Log an informational message (level INFO)
     */
    static void info(LogCategory cat, const char* fmt, ...);

    /**
     * @brief Log a debug message (level DEBUG)
     */
    static void debug(LogCategory cat, const char* fmt, ...);

    /**
     * @brief Log a trace message (level TRACE)
     */
    static void trace(LogCategory cat, const char* fmt, ...);

    /**
     * @brief Process a logging command from serial input
     * @param cmd The command string (e.g., "level debug", "enable radio")
     */
    static void processCommand(const String& cmd);

    /**
     * @brief Print help text showing available commands
     */
    static void printHelp();

    /**
     * @brief Print current logger configuration
     */
    static void printStatus();

    /**
     * @brief Get current configuration (for inspection)
     */
    static const LogConfig& getConfig() { return config; }

    /**
     * @brief Set callback to check if text logging is allowed
     *
     * Used to suppress all text logs when in TELEMETRY_BINARY mode
     * to prevent corrupting the binary stream.
     *
     * @param callback Function that returns true if text logging is allowed
     */
    static void setTextLoggingAllowedCallback(bool (*callback)());

private:
    static LogConfig config;
    static bool (*textLoggingAllowedCallback)();

    /**
     * @brief Check if a message should be logged
     * @param level The message severity level
     * @param cat The message category
     * @return true if message should be logged
     */
    static bool shouldLog(LogLevel level, LogCategory cat);

    /**
     * @brief Convert log level to string
     */
    static const char* levelToString(LogLevel level);

    /**
     * @brief Convert category to 3-4 character abbreviation
     */
    static const char* categoryToString(LogCategory cat);

    /**
     * @brief Print message prefix (timestamp, category, level)
     */
    static void printPrefix(LogLevel level, LogCategory cat);

    /**
     * @brief Internal logging implementation
     */
    static void logImpl(LogLevel level, LogCategory cat, const char* fmt, va_list args);

    /**
     * @brief Parse category name string to enum
     */
    static bool parseCategoryName(const String& name, LogCategory& outCat);
};

// ============================================================================
// Convenience Macros
// ============================================================================

#define LOG_ERROR(cat, ...) Logger::error(LogCategory::cat, __VA_ARGS__)
#define LOG_WARN(cat, ...)  Logger::warn(LogCategory::cat, __VA_ARGS__)
#define LOG_INFO(cat, ...)  Logger::info(LogCategory::cat, __VA_ARGS__)
#define LOG_DEBUG(cat, ...) Logger::debug(LogCategory::cat, __VA_ARGS__)
#define LOG_TRACE(cat, ...) Logger::trace(LogCategory::cat, __VA_ARGS__)
