# RC Transmitter Firmware

A simplified PlatformIO project for ESP32-C3 based RC controller transmitter that communicates with a drone receiver via ESP-NOW protocol.

## Features

- **50 Hz packet transmission rate** for reliable control
- **ESP-NOW wireless protocol** on Wi-Fi channel 1
- **4-channel RC control**: Throttle (latched/integrator), Yaw, Pitch, Roll
- **ARM/DISARM toggle** with debounce protection
- **Real-time OLED display** with control status
- **Simple center-based calibration** system
- **IIR filtering** for smooth control response

## Hardware Requirements

### MCU
- ESP32-C3 Super Mini (or compatible ESP32-C3 board)

### Display
- SSD1306 128×32 OLED display (I²C)
  - VCC → 3.3V
  - GND → GND
  - SDA → GPIO 8
  - SCL → GPIO 9

### Controls
- 2× PS2 analog joysticks (4 total axes)
  - Throttle → GPIO 0 (integrator mode - stick controls rate)
  - Yaw → GPIO 1 (proportional control)
  - Pitch → GPIO 4 (proportional control, inverted)
  - Roll → GPIO 2 (proportional control)
- 1× Tactile button (ARM toggle)
  - One side → GND
  - Other side → GPIO 7 (internal pullup enabled)

### Power Supply
- 3×AA NiMH batteries
- LDO regulator (SPX5205-3.3 or similar) → 3.3V
- Schottky diode (1N5819) for reverse protection

## Software Setup

### Prerequisites
- [VS Code](https://code.visualstudio.com/)
- [PlatformIO IDE extension](https://platformio.org/install/ide?install=vscode)

### Build Instructions

1. Clone or download this repository
2. Open the project folder in VS Code with PlatformIO
3. Connect your ESP32-C3 board via USB
4. Build and upload:
   ```bash
   # Using PlatformIO CLI
   pio run --target upload --target monitor
   
   # Or use VS Code PlatformIO extension buttons:
   # - Click "Build" (✓) to compile
   # - Click "Upload" (→) to flash
   # - Click "Monitor" (🔌) to view serial output
   ```

### Configuration

#### Drone MAC Address
The drone MAC address is configured in `include/config.h`:
```cpp
#define DEFAULT_DRONE_MAC {0xD8, 0x3B, 0xDA, 0x74, 0x83, 0x68}
```

To change the MAC address:
1. Edit `include/config.h` and update the `DEFAULT_DRONE_MAC` value
2. Rebuild and upload the firmware

#### Other Configuration Options
Edit `include/config.h` to modify:
- Pin assignments
- Packet transmission rate (50 Hz default)
- Control parameters (deadzone, IIR filtering)
- ADC settings and sample counts

## Operation

### Initial Calibration
1. Power on the transmitter
2. The system will automatically start calibration
3. **Center Calibration**: Hold all sticks in neutral position for the calibration period
4. Calibration complete - centers are recorded for all axes
5. **Throttle starts at zero** - stick position controls throttle rate of change

### Control Behavior

#### Throttle (Integrator Mode)
- Stick at center: No throttle change
- Stick forward: Throttle increases at rate proportional to stick deflection  
- Stick backward: Throttle decreases at rate proportional to stick deflection
- Throttle value integrates (accumulates) and is clamped to 0-1000 range
- **Always starts at zero on power-up**

#### Yaw, Pitch, Roll (Proportional Mode)
- Stick position directly controls output value
- Center position = 0 output
- Full deflection = ±1000 output  
- PITCH axis is inverted in software
- IIR filtering provides smooth response

### ARM/DISARM Operation
- Press the ARM button to toggle armed/disarmed state
- No throttle interlock - can ARM at any throttle position
- Debounced with 100ms protection against false triggers
- ARM state is transmitted in every packet

## Protocol Specification

### Packet Format
```cpp
struct RcPacket {
    uint8_t  magic;     // 0xA5
    uint8_t  version;   // 1
    uint16_t seq;       // Sequence counter
    uint16_t thr;       // Throttle: 0..1000
    int16_t  yaw;       // Yaw: -1000..1000
    int16_t  pitch;     // Pitch: -1000..1000 (inverted)
    int16_t  roll;      // Roll: -1000..1000
    uint8_t  flags;     // Bit 0: ARM state
    uint8_t  rssi_hint; // RSSI info (currently 0)
    uint16_t crc;       // CRC-16/X.25
};
```

### Communication
- **Protocol**: ESP-NOW
- **Channel**: Wi-Fi Channel 1
- **Rate**: 50 Hz (20ms intervals)
- **CRC**: CRC-16/X.25 for packet integrity
- **Sequence**: 16-bit counter for packet loss detection

## Troubleshooting

### Build Issues
- Ensure PlatformIO is properly installed
- Verify ESP32 platform and libraries are downloaded
- Check that the correct board is selected (esp32-c3-devkitm-1)

### Upload Issues
- Verify USB cable connection
- Hold BOOT button while connecting USB (if needed for ESP32-C3)
- Check COM port selection in PlatformIO

### Runtime Issues
- **Display not working**: Check I²C wiring (SDA/SCL pins)
- **No radio transmission**: Verify ESP-NOW initialization in serial monitor
- **Erratic control**: Check joystick wiring and power supply stability
- **ARM button not working**: Verify button wiring and GPIO 7 connection
- **Throttle not responding**: Remember throttle is integrator mode - stick controls rate, not position

### Serial Debug
Connect to serial monitor (115200 baud) to see:
- Initialization status
- Error messages during startup
- Calibration values

## Code Structure

```
src/
├── main.cpp          # Main application loop and OLED handling
├── control.cpp       # Joystick reading, filtering, and ARM handling
├── protocol.cpp      # Packet format and CRC calculation
└── radio.cpp         # ESP-NOW communication

include/
├── config.h          # Hardware and system configuration
├── control.h         # Control system interface
├── protocol.h        # Communication protocol definitions
└── radio.h           # Radio system interface
```

## Key Differences from Complex Version

This simplified version matches the reference Arduino code exactly:

- **Simple calibration**: Center-point calibration only (no min/max tracking)
- **Integrator throttle**: Stick controls throttle rate, not direct position
- **Direct OLED control**: No separate display manager class
- **Basic IIR filtering**: Single-pole filter on joystick readings
- **No ARM interlock**: Can ARM at any throttle position
- **50 Hz operation**: Matches reference code timing
- **Simplified structure**: Fewer classes, more direct control flow

## Contributing

This project maintains compatibility with the reference Arduino implementation while providing a clean PlatformIO structure for development and maintenance.

## License

This project is open source. See individual source files for specific license information.