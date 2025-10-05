# Transmitter Firmware: Logging System Implementation Request

## Objective

Implement a professional, modular logging system for the transmitter firmware that matches the architecture and capabilities of the drone receiver's logging system. The goal is to maintain consistency across both firmware codebases for easier debugging and development.

## Requirements Overview

You need to design and implement a **runtime-configurable logging system** with the following capabilities:

### 1. Hierarchical Log Levels

Implement a severity-based logging hierarchy that allows filtering messages by importance. The system should support multiple levels ranging from critical errors to verbose trace output. Users should be able to set a global log level that filters out less important messages.

**Expected behavior**: Setting a log level should enable that level and all more severe levels. For example, if "warnings" are enabled, "errors" should also appear.

### 2. Category-Based Filtering

Implement a category system that allows enabling/disabling logs from specific subsystems or modules. This should allow developers to focus on specific parts of the system without noise from other components.

**Key requirements**:
- Categories should be independently toggleable
- Multiple categories can be enabled simultaneously
- Efficient implementation (consider using bitmasks for performance)
- Each category should represent a logical subsystem (e.g., radio, display, battery, inputs)

**Suggested categories for transmitter** (adapt as needed):
- System initialization and core functionality
- RC input processing (joysticks, switches)
- Radio/ESP-NOW communication
- Display/UI updates
- Battery monitoring
- Configuration management
- Button/input handling
- Telemetry reception and processing

### 3. Runtime Configuration via Serial

The system must be configurable at runtime through serial commands without requiring firmware recompilation. Users should be able to:

- View current logging configuration
- Change log level dynamically
- Enable/disable specific categories
- Access help/documentation
- Use preset configurations for common debugging scenarios

**Expected command interface**:
- Simple text-based commands (e.g., "enable radio", "level debug")
- Status query command showing current settings
- Help command listing available options
- Quick preset configurations (e.g., "verbose", "quiet", "basic")

### 4. Clean, Maintainable Code Structure

The implementation should follow professional embedded software practices:

- **Modular design**: Separate header and implementation files
- **Easy integration**: Simple macro-based API for logging calls
- **Minimal dependencies**: Avoid external libraries where possible
- **Consistent formatting**: Clear, readable log output
- **Performance conscious**: Zero-overhead options for release builds
- **Well-documented**: Clear comments and usage examples

### 5. Formatting and Output

Implement clean, parseable log output with:

- Consistent message format across all log levels
- Optional timestamps for timing analysis
- Category labels for quick identification
- Printf-style formatting support for variables
- Configurable output verbosity (show/hide timestamps, levels, etc.)

## Technical Specifications

### API Design

Your logging API should be **simple to use** throughout the codebase:

```cpp
// Example of desired usage (adapt syntax as needed)
LOG_ERROR(CATEGORY, "format string", args...);
LOG_WARN(CATEGORY, "format string", args...);
LOG_INFO(CATEGORY, "format string", args...);
LOG_DEBUG(CATEGORY, "format string", args...);
```

### Memory Constraints

- Keep memory footprint minimal (this is an embedded system)
- Use static allocation where possible
- Consider buffer sizes carefully (256 bytes for formatting is typical)
- Avoid dynamic memory allocation

### Performance Considerations

- Filtering should be very fast (O(1) operations)
- Consider compile-time optimization options
- Avoid logging in time-critical interrupt handlers
- Provide options to completely disable logging in release builds

## Implementation Guidance

### Phase 1: Core Infrastructure
1. Define log levels (enumeration or constants)
2. Define log categories (using efficient representation)
3. Implement basic filtering logic (level + category checks)
4. Create simple output function with formatting

### Phase 2: Configuration System
1. Create configuration structure to hold settings
2. Implement serial command parser
3. Add runtime enable/disable for categories
4. Add runtime level adjustment
5. Implement status query functionality

### Phase 3: Integration & Polish
1. Create convenient macros for logging
2. Add preset configurations
3. Add help system
4. Document usage with examples
5. Test thoroughly with various configurations

### Phase 4: Advanced Features (Optional)
1. Assertions for runtime validation
2. Conditional logging macros (compile-time optimization)
3. Domain-specific helper macros
4. Performance measurement helpers

## Expected Deliverables

1. **Header files** defining the logging API and public interface
2. **Implementation files** containing the logging logic
3. **Integration examples** showing how to use the system in existing code
4. **Serial command documentation** (help text) built into the firmware
5. **Sensible defaults** that work out-of-box for typical debugging

## Design Consistency Requirements

While you should design this system independently, ensure these aspects match the drone receiver firmware:

- **Same log level hierarchy** (use equivalent severity names)
- **Similar serial command syntax** (for user familiarity)
- **Comparable category granularity** (enough detail, not overwhelming)
- **Matching output format** (makes log comparison easier)
- **Consistent macro naming** (LOG_ERROR, LOG_INFO, etc.)

## Testing Requirements

Verify your implementation by:

1. Testing all log levels filter correctly
2. Testing all categories can be toggled independently
3. Testing all serial commands work as documented
4. Testing log output is clean and readable
5. Testing performance impact is minimal
6. Testing memory usage is acceptable

## Example Usage Scenarios

Your logging system should support scenarios like these:

**Scenario 1: Debugging RC input issues**
```
User enables INPUTS category at DEBUG level
Logs show joystick values, button states, and calculations
Other categories remain quiet to reduce noise
```

**Scenario 2: Investigating radio communication problems**
```
User enables RADIO category at TRACE level
Logs show packet transmission, acknowledgments, retries
Detailed packet contents visible for analysis
```

**Scenario 3: Production/Flight Mode**
```
User sets level to ERROR only
User enables SYSTEM and BATTERY categories
Only critical messages appear, minimal performance impact
```

**Scenario 4: Full System Debug**
```
User runs "verbose" preset command
All categories enabled at DEBUG level
Complete system visibility for comprehensive troubleshooting
```

## Success Criteria

Your implementation will be successful if:

- ✅ Developers can easily add logging to new code
- ✅ Users can configure logging via serial without reflashing
- ✅ Log output is clean, consistent, and informative
- ✅ Performance impact is negligible in typical usage
- ✅ System matches drone receiver logging architecture
- ✅ Code is well-structured and maintainable
- ✅ Documentation (help text) is clear and complete

## Notes

- **Do NOT copy code** - design your own implementation suited to the transmitter's architecture
- **DO maintain consistency** with the reference implementation provided below
- **Consider the transmitter's specific needs** when choosing categories and features
- **Keep it simple** - don't over-engineer, but make it robust and useful
- **Think about your users** - make configuration intuitive and help text clear

---

## REFERENCE IMPLEMENTATION SPECIFICATION

The drone receiver firmware uses the following logging architecture. **You must implement the same structure** to maintain consistency between transmitter and receiver.

### Log Level Hierarchy

Use these **exact** log levels and numeric values:

```cpp
NONE    = 0  // No logging
ERROR   = 1  // Critical errors only
WARN    = 2  // Warnings and errors
INFO    = 3  // General information (default)
DEBUG   = 4  // Detailed debugging
TRACE   = 5  // Very verbose tracing
```

**Filtering rule**: A message at level L is logged if `L <= global_level`

Example: If `global_level = WARN`, then ERROR and WARN messages appear, but INFO/DEBUG/TRACE are suppressed.

### Category Implementation

Categories **must** be implemented as a 32-bit bitmask for efficient filtering:

```cpp
// Example category definitions (adapt names to transmitter)
SYSTEM   = 0x00000001  // Bit 0
INPUTS   = 0x00000002  // Bit 1
RADIO    = 0x00000004  // Bit 2
DISPLAY  = 0x00000008  // Bit 3
BATTERY  = 0x00000010  // Bit 4
TELEM    = 0x00000020  // Bit 5
CONFIG   = 0x00000040  // Bit 6
UI       = 0x00000080  // Bit 7
CALIB    = 0x00000100  // Bit 8
// ... add more as needed (up to 32 categories)
ALL      = 0xFFFFFFFF  // All bits set
```

**Operations**:
- Enable multiple: `enabled_categories = CAT_A | CAT_B | CAT_C`
- Check if enabled: `if (enabled_categories & CAT_A != 0)`
- Disable specific: `enabled_categories = enabled_categories & (~CAT_A)`

**Filtering rule**: A message in category C is logged if `(enabled_categories & C) != 0`

### Serial Command Interface

Implement these **exact** commands for consistency:

```
Command                 Description
-------                 -----------
help, h                 Show help menu
status, s               Show current configuration

level none              Set log level to NONE (disable all)
level error             Set log level to ERROR
level warn              Set log level to WARN
level info              Set log level to INFO (default)
level debug             Set log level to DEBUG
level trace             Set log level to TRACE (most verbose)

enable <category>       Enable specific category (e.g., "enable radio")
disable <category>      Disable specific category (e.g., "disable display")
enable all              Enable all categories

quiet                   Preset: Disable all logging
basic                   Preset: Enable only essential categories (system, battery)
verbose                 Preset: Enable all categories at DEBUG level
```

**Command parsing**:
- Commands are case-insensitive
- Trim whitespace
- Parse via `String.toLowerCase()` and `String.startsWith()`

### Output Format

**Standard format** (default):
```
<ABBREV>: <message>
```

Examples:
```
SYS: Logger initialized
RAD: Packet sent: len=16, seq=42
BAT: Voltage: 3.87V
INP: Stick X=512, Y=498
```

**With timestamp** (optional, configurable):
```
[<millis>] <ABBREV>: <message>
```

Examples:
```
[00012345] SYS: System ready
[00012456] RAD: TX complete
[00012512] BAT: Low battery warning
```

**Category abbreviations**: Use 3-4 character codes for readability:
- `SYS` = System
- `INP` = Inputs
- `RAD` = Radio
- `DSP` = Display
- `BAT` = Battery
- `TEL` = Telemetry
- `CFG` = Config
- `UI ` = User Interface
- `CAL` = Calibration

### API Macros

Provide these **exact** macro names:

```cpp
LOG_ERROR(category, format, ...)
LOG_WARN(category, format, ...)
LOG_INFO(category, format, ...)
LOG_DEBUG(category, format, ...)
LOG_TRACE(category, format, ...)
```

**Usage examples**:
```cpp
LOG_ERROR(RADIO, "TX failed: error=%d", err_code);
LOG_WARN(BATTERY, "Low voltage: %.2fV", voltage);
LOG_INFO(SYSTEM, "Transmitter initialized");
LOG_DEBUG(INPUTS, "Stick: x=%d, y=%d", stick_x, stick_y);
LOG_TRACE(RADIO, "Packet bytes: %02X %02X %02X", b0, b1, b2);
```

### Configuration Structure

Use this structure to store logger state:

```cpp
struct LogConfig {
    uint8_t  global_level;           // 0-5 (NONE to TRACE)
    uint32_t enabled_categories;     // Bitmask of enabled categories
    bool     show_timestamp;         // Include [millis] prefix
    bool     show_category;          // Include category abbreviation
    bool     show_level;             // Include level name (optional)
};
```

**Default settings**:
```cpp
global_level = INFO                              // Level 3
enabled_categories = SYSTEM | BATTERY            // Essential only
show_timestamp = false                           // Off by default
show_category = true                             // Always show category
show_level = false                               // Usually unnecessary
```

### Filtering Logic

A message is logged **only if both conditions are true**:

1. **Level check**: `message_level <= global_level`
2. **Category check**: `(enabled_categories & message_category) != 0`

Implement filtering **before** formatting for performance:

```cpp
bool shouldLog(LogLevel level, LogCategory category) {
    if (level > global_level) return false;
    if ((enabled_categories & category) == 0) return false;
    return true;
}
```

### Implementation Pattern

**File structure**:
```
transmitter/
├── include/
│   ├── logger.h        // Public API, macros, enums
│   └── log.h           // Optional: advanced features
└── src/
    └── logger.cpp      // Implementation
```

**Minimal logger.h**:
```cpp
#pragma once
#include <Arduino.h>

// Log levels
enum class LogLevel : uint8_t {
    NONE = 0, ERROR = 1, WARN = 2, INFO = 3, DEBUG = 4, TRACE = 5
};

// Log categories (bitmask)
enum class LogCategory : uint32_t {
    SYSTEM   = 0x00000001,
    INPUTS   = 0x00000002,
    RADIO    = 0x00000004,
    DISPLAY  = 0x00000008,
    BATTERY  = 0x00000010,
    TELEM    = 0x00000020,
    CONFIG   = 0x00000040,
    UI       = 0x00000080,
    ALL      = 0xFFFFFFFF
};

// Bitwise operators for categories
inline LogCategory operator|(LogCategory a, LogCategory b) {
    return static_cast<LogCategory>(static_cast<uint32_t>(a) | static_cast<uint32_t>(b));
}
inline LogCategory operator&(LogCategory a, LogCategory b) {
    return static_cast<LogCategory>(static_cast<uint32_t>(a) & static_cast<uint32_t>(b));
}
inline LogCategory operator~(LogCategory a) {
    return static_cast<LogCategory>(~static_cast<uint32_t>(a));
}

// Configuration
struct LogConfig {
    LogLevel global_level = LogLevel::INFO;
    LogCategory enabled_categories = LogCategory::SYSTEM | LogCategory::BATTERY;
    bool show_timestamp = false;
    bool show_category = true;
    bool show_level = false;
};

// Logger class
class Logger {
public:
    static void init();
    static void setLevel(LogLevel level);
    static void enableCategory(LogCategory cat);
    static void disableCategory(LogCategory cat);

    static void error(LogCategory cat, const char* fmt, ...);
    static void warn(LogCategory cat, const char* fmt, ...);
    static void info(LogCategory cat, const char* fmt, ...);
    static void debug(LogCategory cat, const char* fmt, ...);
    static void trace(LogCategory cat, const char* fmt, ...);

    static void processCommand(const String& cmd);
    static void printHelp();
    static void printStatus();

private:
    static LogConfig config;
    static bool shouldLog(LogLevel level, LogCategory cat);
    static const char* levelToString(LogLevel level);
    static const char* categoryToString(LogCategory cat);
    static void printPrefix(LogLevel level, LogCategory cat);
};

// Convenience macros
#define LOG_ERROR(cat, ...) Logger::error(LogCategory::cat, __VA_ARGS__)
#define LOG_WARN(cat, ...)  Logger::warn(LogCategory::cat, __VA_ARGS__)
#define LOG_INFO(cat, ...)  Logger::info(LogCategory::cat, __VA_ARGS__)
#define LOG_DEBUG(cat, ...) Logger::debug(LogCategory::cat, __VA_ARGS__)
#define LOG_TRACE(cat, ...) Logger::trace(LogCategory::cat, __VA_ARGS__)
```

**Implementation pattern** (logger.cpp):
```cpp
#include "logger.h"
#include <stdarg.h>

LogConfig Logger::config = {};

void Logger::init() {
    Serial.begin(115200);
    info(LogCategory::SYSTEM, "Logger initialized");
    printHelp();
}

void Logger::error(LogCategory cat, const char* fmt, ...) {
    if (!shouldLog(LogLevel::ERROR, cat)) return;

    printPrefix(LogLevel::ERROR, cat);

    va_list args;
    va_start(args, fmt);
    char buffer[256];
    vsnprintf(buffer, sizeof(buffer), fmt, args);
    va_end(args);

    Serial.println(buffer);
}

// ... implement warn, info, debug, trace similarly

bool Logger::shouldLog(LogLevel level, LogCategory cat) {
    if (level > config.global_level) return false;
    if ((static_cast<uint32_t>(config.enabled_categories & cat)) == 0) return false;
    return true;
}

void Logger::printPrefix(LogLevel level, LogCategory cat) {
    if (config.show_timestamp) {
        Serial.printf("[%08lu] ", millis());
    }
    if (config.show_category) {
        Serial.printf("%s: ", categoryToString(cat));
    }
}

// ... implement command parsing, help, status
```

### Help Text Format

When user types "help", display:

```
=== LOGGER COMMANDS ===
help/h          - Show this help
status/s        - Show current config
level <level>   - Set log level (none/error/warn/info/debug/trace)
enable <cat>    - Enable category
disable <cat>   - Disable category
Categories: all, system, inputs, radio, display, battery, telem, config, ui
Presets:
quiet          - Disable all logging
basic          - Essential categories only
verbose        - Enable everything
=======================
```

### Status Output Format

When user types "status", display:

```
Log Level: INFO
Categories: 0x00000011
Enabled: system, battery
```

---

## Implementation Checklist

- [ ] Create `logger.h` with enums, config struct, Logger class
- [ ] Create `logger.cpp` with implementation
- [ ] Implement all 5 log level functions (error/warn/info/debug/trace)
- [ ] Implement `shouldLog()` filtering function
- [ ] Implement `processCommand()` parser for serial commands
- [ ] Implement `printHelp()` and `printStatus()`
- [ ] Create `LOG_ERROR/WARN/INFO/DEBUG/TRACE` macros
- [ ] Add bitwise operators for LogCategory
- [ ] Test all serial commands work
- [ ] Test filtering works correctly
- [ ] Integrate into transmitter main code

---

**Priority**: Medium-High
**Estimated Effort**: 3-4 hours
**Dependencies**: None (standalone feature)
**Target**: Next firmware revision

**Deliverables**:
1. `logger.h` and `logger.cpp` matching the structure above
2. Working serial command interface with all specified commands
3. At least 3 integration examples in transmitter code
4. Verified output format matches specification
