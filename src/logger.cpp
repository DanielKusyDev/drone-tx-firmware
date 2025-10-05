#include "logger.h"
#include <stdarg.h>

// Static member initialization
LogConfig Logger::config = {};

// ============================================================================
// Public API
// ============================================================================

void Logger::init() {
    // Serial should already be initialized by main()
    info(LogCategory::SYSTEM, "Logger initialized - type 'help' for commands");
}

void Logger::setLevel(LogLevel level) {
    config.global_level = level;
    info(LogCategory::SYSTEM, "Log level set to %s", levelToString(level));
}

void Logger::enableCategory(LogCategory cat) {
    config.enabled_categories |= cat;
}

void Logger::disableCategory(LogCategory cat) {
    config.enabled_categories &= ~cat;
}

void Logger::enableAllCategories() {
    config.enabled_categories = LogCategory::ALL;
}

// ============================================================================
// Logging Functions
// ============================================================================

void Logger::error(LogCategory cat, const char* fmt, ...) {
    if (!shouldLog(LogLevel::ERROR, cat)) return;

    va_list args;
    va_start(args, fmt);
    logImpl(LogLevel::ERROR, cat, fmt, args);
    va_end(args);
}

void Logger::warn(LogCategory cat, const char* fmt, ...) {
    if (!shouldLog(LogLevel::WARN, cat)) return;

    va_list args;
    va_start(args, fmt);
    logImpl(LogLevel::WARN, cat, fmt, args);
    va_end(args);
}

void Logger::info(LogCategory cat, const char* fmt, ...) {
    if (!shouldLog(LogLevel::INFO, cat)) return;

    va_list args;
    va_start(args, fmt);
    logImpl(LogLevel::INFO, cat, fmt, args);
    va_end(args);
}

void Logger::debug(LogCategory cat, const char* fmt, ...) {
    if (!shouldLog(LogLevel::DEBUG, cat)) return;

    va_list args;
    va_start(args, fmt);
    logImpl(LogLevel::DEBUG, cat, fmt, args);
    va_end(args);
}

void Logger::trace(LogCategory cat, const char* fmt, ...) {
    if (!shouldLog(LogLevel::TRACE, cat)) return;

    va_list args;
    va_start(args, fmt);
    logImpl(LogLevel::TRACE, cat, fmt, args);
    va_end(args);
}

// ============================================================================
// Command Processing
// ============================================================================

void Logger::processCommand(const String& cmd) {
    String trimmed = cmd;
    trimmed.trim();
    trimmed.toLowerCase();

    if (trimmed.isEmpty()) return;

    // Help commands
    if (trimmed == "help" || trimmed == "h") {
        printHelp();
        return;
    }

    // Status command
    if (trimmed == "status" || trimmed == "s") {
        printStatus();
        return;
    }

    // Level commands
    if (trimmed.startsWith("level ")) {
        String levelStr = trimmed.substring(6);
        levelStr.trim();

        if (levelStr == "none") setLevel(LogLevel::NONE);
        else if (levelStr == "error") setLevel(LogLevel::ERROR);
        else if (levelStr == "warn") setLevel(LogLevel::WARN);
        else if (levelStr == "info") setLevel(LogLevel::INFO);
        else if (levelStr == "debug") setLevel(LogLevel::DEBUG);
        else if (levelStr == "trace") setLevel(LogLevel::TRACE);
        else Serial.println("[LOG] Unknown level. Use: none/error/warn/info/debug/trace");
        return;
    }

    // Enable commands
    if (trimmed.startsWith("enable ")) {
        String catStr = trimmed.substring(7);
        catStr.trim();

        if (catStr == "all") {
            enableAllCategories();
            Serial.println("[LOG] All categories enabled");
        } else {
            LogCategory cat;
            if (parseCategoryName(catStr, cat)) {
                enableCategory(cat);
                Serial.printf("[LOG] Category '%s' enabled\n", catStr.c_str());
            } else {
                Serial.printf("[LOG] Unknown category: %s\n", catStr.c_str());
            }
        }
        return;
    }

    // Disable commands
    if (trimmed.startsWith("disable ")) {
        String catStr = trimmed.substring(8);
        catStr.trim();

        LogCategory cat;
        if (parseCategoryName(catStr, cat)) {
            disableCategory(cat);
            Serial.printf("[LOG] Category '%s' disabled\n", catStr.c_str());
        } else {
            Serial.printf("[LOG] Unknown category: %s\n", catStr.c_str());
        }
        return;
    }

    // Preset commands
    if (trimmed == "quiet") {
        setLevel(LogLevel::NONE);
        config.enabled_categories = static_cast<LogCategory>(0);
        Serial.println("[LOG] Preset: Quiet mode (all logging disabled)");
        return;
    }

    if (trimmed == "basic") {
        setLevel(LogLevel::INFO);
        config.enabled_categories = LogCategory::SYSTEM | LogCategory::BATTERY;
        Serial.println("[LOG] Preset: Basic mode (essential categories only)");
        return;
    }

    if (trimmed == "verbose") {
        setLevel(LogLevel::DEBUG);
        enableAllCategories();
        Serial.println("[LOG] Preset: Verbose mode (all categories at DEBUG level)");
        return;
    }

    // Unknown command
    Serial.printf("[LOG] Unknown command: %s (type 'help' for commands)\n", trimmed.c_str());
}

void Logger::printHelp() {
    Serial.println();
    Serial.println("=== LOGGER COMMANDS ===");
    Serial.println("help, h          - Show this help");
    Serial.println("status, s        - Show current configuration");
    Serial.println();
    Serial.println("level <level>    - Set log level:");
    Serial.println("                   none/error/warn/info/debug/trace");
    Serial.println();
    Serial.println("enable <cat>     - Enable category");
    Serial.println("disable <cat>    - Disable category");
    Serial.println("enable all       - Enable all categories");
    Serial.println();
    Serial.println("Categories:");
    Serial.println("  system, inputs, radio, oled, battery,");
    Serial.println("  telem, config, ui, calib");
    Serial.println();
    Serial.println("Presets:");
    Serial.println("  quiet          - Disable all logging");
    Serial.println("  basic          - Essential categories only");
    Serial.println("  verbose        - Enable everything at DEBUG");
    Serial.println("=======================");
    Serial.println();
}

void Logger::printStatus() {
    Serial.println();
    Serial.println("=== LOGGER STATUS ===");
    Serial.printf("Log Level: %s\n", levelToString(config.global_level));
    Serial.printf("Categories: 0x%08X\n", static_cast<uint32_t>(config.enabled_categories));

    // List enabled categories
    Serial.print("Enabled: ");
    bool first = true;
    uint32_t cats = static_cast<uint32_t>(config.enabled_categories);

    if (cats & static_cast<uint32_t>(LogCategory::SYSTEM)) {
        Serial.print(first ? "system" : ", system");
        first = false;
    }
    if (cats & static_cast<uint32_t>(LogCategory::INPUTS)) {
        Serial.print(first ? "inputs" : ", inputs");
        first = false;
    }
    if (cats & static_cast<uint32_t>(LogCategory::RADIO)) {
        Serial.print(first ? "radio" : ", radio");
        first = false;
    }
    if (cats & static_cast<uint32_t>(LogCategory::OLED)) {
        Serial.print(first ? "oled" : ", oled");
        first = false;
    }
    if (cats & static_cast<uint32_t>(LogCategory::BATTERY)) {
        Serial.print(first ? "battery" : ", battery");
        first = false;
    }
    if (cats & static_cast<uint32_t>(LogCategory::TELEM)) {
        Serial.print(first ? "telem" : ", telem");
        first = false;
    }
    if (cats & static_cast<uint32_t>(LogCategory::CONFIG)) {
        Serial.print(first ? "config" : ", config");
        first = false;
    }
    if (cats & static_cast<uint32_t>(LogCategory::UI)) {
        Serial.print(first ? "ui" : ", ui");
        first = false;
    }
    if (cats & static_cast<uint32_t>(LogCategory::CALIB)) {
        Serial.print(first ? "calib" : ", calib");
        first = false;
    }

    if (first) Serial.print("(none)");
    Serial.println();

    Serial.printf("Timestamp: %s\n", config.show_timestamp ? "ON" : "OFF");
    Serial.println("=====================");
    Serial.println();
}

// ============================================================================
// Private Implementation
// ============================================================================

bool Logger::shouldLog(LogLevel level, LogCategory cat) {
    // Level check: message must be at or below global level
    if (level > config.global_level) return false;

    // Category check: message category must be enabled
    uint32_t catBits = static_cast<uint32_t>(cat);
    uint32_t enabledBits = static_cast<uint32_t>(config.enabled_categories);
    if ((enabledBits & catBits) == 0) return false;

    return true;
}

const char* Logger::levelToString(LogLevel level) {
    switch (level) {
        case LogLevel::NONE:  return "NONE";
        case LogLevel::ERROR: return "ERROR";
        case LogLevel::WARN:  return "WARN";
        case LogLevel::INFO:  return "INFO";
        case LogLevel::DEBUG: return "DEBUG";
        case LogLevel::TRACE: return "TRACE";
        default: return "UNKNOWN";
    }
}

const char* Logger::categoryToString(LogCategory cat) {
    switch (cat) {
        case LogCategory::SYSTEM:  return "SYS";
        case LogCategory::INPUTS:  return "INP";
        case LogCategory::RADIO:   return "RAD";
        case LogCategory::OLED:    return "DSP";
        case LogCategory::BATTERY: return "BAT";
        case LogCategory::TELEM:   return "TEL";
        case LogCategory::CONFIG:  return "CFG";
        case LogCategory::UI:      return "UI ";
        case LogCategory::CALIB:   return "CAL";
        default: return "???";
    }
}

void Logger::printPrefix(LogLevel level, LogCategory cat) {
    if (config.show_timestamp) {
        Serial.printf("[%08lu] ", millis());
    }

    if (config.show_level) {
        Serial.printf("%s: ", levelToString(level));
    }

    if (config.show_category) {
        Serial.printf("%s: ", categoryToString(cat));
    }
}

void Logger::logImpl(LogLevel level, LogCategory cat, const char* fmt, va_list args) {
    printPrefix(level, cat);

    char buffer[256];
    vsnprintf(buffer, sizeof(buffer), fmt, args);
    Serial.println(buffer);
}

bool Logger::parseCategoryName(const String& name, LogCategory& outCat) {
    if (name == "system") { outCat = LogCategory::SYSTEM; return true; }
    if (name == "inputs") { outCat = LogCategory::INPUTS; return true; }
    if (name == "radio")  { outCat = LogCategory::RADIO;  return true; }
    if (name == "oled" || name == "display") { outCat = LogCategory::OLED; return true; }
    if (name == "battery"){ outCat = LogCategory::BATTERY;return true; }
    if (name == "telem")  { outCat = LogCategory::TELEM;  return true; }
    if (name == "config") { outCat = LogCategory::CONFIG; return true; }
    if (name == "ui")     { outCat = LogCategory::UI;     return true; }
    if (name == "calib")  { outCat = LogCategory::CALIB;  return true; }
    return false;
}
