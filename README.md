# RC Transmitter Firmware

A simplified PlatformIO project for ESP32-C3 based RC controller transmitter that communicates with a drone receiver via ESP-NOW protocol.

## Features

### Core RC Functionality
- **50 Hz packet transmission rate** for reliable control
- **ESP-NOW wireless protocol** on Wi-Fi channel 1
- **4-channel RC control**: Throttle (latched/integrator), Yaw, Pitch, Roll
- **ARM/DISARM toggle** with debounce protection
- **Simple center-based calibration** system
- **IIR filtering** for smooth control response

### Telemetry System
- **Bidirectional communication** - Receives telemetry from drone
- **Dual OLED display modes**:
  - **Normal view**: ARM status, throttle, estimated angles, yaw rate, telemetry FPS
  - **Debug view**: Setpoints, rate values, PID outputs for tuning
- **Button-controlled view switching** - Long press ARM button (1.5s) to toggle views
- **Real-time CSV data logging** over USB Serial for analysis
- **Connection quality monitoring** with drop count tracking
- **CRC validation** for telemetry packet integrity

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
- 1× Tactile button (ARM/Display toggle)
  - One side → GND
  - Other side → GPIO 7 (internal pullup enabled)
  - **Short press** (< 0.5s): Toggle ARM state
  - **Long press** (> 1.5s): Toggle OLED display view (Normal ↔ Debug)

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

**Finding MAC Addresses:**
- **Transmitter MAC**: Connect via USB Serial and send command `M`
- **Drone MAC**: Check drone's serial output or use WiFi scanner tools

#### Telemetry Setup
For bidirectional telemetry to work:
1. **Drone firmware must support telemetry transmission** with packet magic `0xB5`
2. **MAC addresses must match**: 
   - Drone must know transmitter's MAC (get with `M` command)
   - Transmitter must know drone's MAC (set in `DEFAULT_DRONE_MAC`)
3. **Same ESP-NOW channel** (Channel 1 default)
4. **Compatible packet format** (see Protocol Specification below)

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
- **Short press** ARM button (< 0.5s) to toggle armed/disarmed state
- **Long press** ARM button (> 1.5s) to switch OLED display views
- No throttle interlock - can ARM at any throttle position
- Debounced with timing-based detection for reliable operation
- ARM state is transmitted in every packet

### Display Modes

#### Normal View
- Line 1: `ARM: ON/OFF THR: 123` - ARM status and current throttle value
- Line 2: `R: 12.3 P: -5.4` - Estimated roll and pitch angles from drone
- Line 3: `YR: 45 FPS: 25` - Yaw rate and telemetry update frequency
- Drop indicator: Small dot appears for every 5 dropped telemetry packets

#### Debug View (for PID tuning)
- Line 1: `setR: 12.3 setP: -5.4` - Roll and pitch setpoints
- Line 2: `rateR: 45 rateP: -23` - Roll and pitch rates
- Line 3: `outR: 123 outP: -45 Y: 67` - PID outputs for roll, pitch, yaw

### CSV Data Logging
Connect to USB Serial (115200 baud) to capture real-time telemetry data:
```
ms,armed,throttle,setR,setP,angR,angP,rateR,rateP,rateY,outR,outP,outY,m1,m2,m3,m4
1234,1,450,12.3,-5.4,10.2,-3.1,45,-23,12,123,-45,67,1200,1150,1180,1220
```

### Serial Commands
While connected to USB Serial (115200 baud), you can use the following commands:
- **`M`** or **`m`**: Display transmitter MAC address
  - Example output: `Transmitter MAC: E4:B3:23:C5:F4:6C`
  - Use this MAC address in drone firmware configuration

## Protocol Specification

### RC Packet Format (Transmitter → Drone)
```cpp
struct RcPacket {
    uint8_t  magic;     // 0xA5
    uint8_t  version;   // 1
    uint16_t seq;       // Sequence counter
    uint16_t thr;       // Throttle: 0..1000
    int16_t  yaw;       // Yaw: -1000..1000
    int16_t  pitch;     // Pitch: -1000..1000 (inverted)
    int16_t  roll;      // Roll: -1000..1000
    uint8_t  flags;     // Bit 0: ARM state, Bit 1: Debug view
    uint8_t  rssi_hint; // RSSI info (currently 0)
    uint16_t crc;       // CRC-16/X.25
};
```

### Telemetry Packet Format (Drone → Transmitter)
```cpp
struct TelemetryPacket {
    uint8_t  magic;      // 0xB5
    uint8_t  version;    // 1
    uint16_t seq;        // Sequence counter
    int16_t  setR_x10;   // Roll setpoint * 10
    int16_t  setP_x10;   // Pitch setpoint * 10
    int16_t  angR_x10;   // Roll angle * 10 (degrees)
    int16_t  angP_x10;   // Pitch angle * 10 (degrees)
    int16_t  rateR_x10;  // Roll rate * 10 (deg/s)
    int16_t  rateP_x10;  // Pitch rate * 10 (deg/s)  
    int16_t  rateY_x10;  // Yaw rate * 10 (deg/s)
    int16_t  outR;       // Roll PID output
    int16_t  outP;       // Pitch PID output
    int16_t  outY;       // Yaw PID output
    uint16_t m1, m2, m3, m4; // Motor outputs
    // ... additional fields
    uint16_t crc;        // CRC-16/X.25
};
```

### Communication
- **Protocol**: ESP-NOW (bidirectional)
- **Channel**: Wi-Fi Channel 1
- **RC Rate**: 50 Hz (20ms intervals) - Transmitter to drone
- **Telemetry Rate**: Variable (~25-50 Hz) - Drone to transmitter  
- **CRC**: CRC-16/X.25 for packet integrity on both directions
- **Sequence**: 16-bit counters for packet loss detection
- **Drop Detection**: Tracks missing telemetry packets for connection quality

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
- **No telemetry display**: 
  - Check drone is powered and transmitting telemetry
  - Verify MAC addresses match between transmitter and drone
  - Look for "Drop:" messages in serial monitor
  - **No `[RECV]` messages = drone not sending telemetry**
  - Use `M` command to get transmitter MAC for drone configuration
- **Display stuck in wrong mode**: Long press ARM button (>1.5s) to toggle views
- **CSV data missing**: Connect USB Serial at 115200 baud, telemetry auto-starts CSV output
- **Telemetry debugging**: 
  - `[RECV]` messages indicate successful packet reception
  - Check packet magic (should be `0xB5`) and CRC validation
  - Verify packet size matches `TelemetryPacket` structure

### Serial Debug
Connect to serial monitor (115200 baud) to see:
- Initialization status
- Error messages during startup  
- Calibration values
- **Real-time CSV telemetry data** (when drone connected)
- Packet drop notifications
- Telemetry frequency measurements
- **Debug commands**: Send `M` to display transmitter MAC address

### Debug Information
- **`[DEBUG]`**: Periodic status every 5 seconds (time, ARM state, throttle, sequence)
- **`[BTN]`**: Button press detection and duration
- **`[RECV]`**: Incoming telemetry packets (only when drone sends data)
- **MAC addresses**: Displayed during startup and on `M` command

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

## Key Features

This implementation balances simplicity with advanced telemetry capabilities:

### Core RC System (matches reference Arduino code)
- **Simple calibration**: Center-point calibration only (no min/max tracking)
- **Integrator throttle**: Stick controls throttle rate, not direct position
- **Direct OLED control**: No separate display manager class
- **Basic IIR filtering**: Single-pole filter on joystick readings
- **No ARM interlock**: Can ARM at any throttle position
- **50 Hz operation**: Matches reference code timing
- **Simplified structure**: Fewer classes, more direct control flow

### Enhanced Telemetry System
- **Bidirectional ESP-NOW**: Maintains RC timing while adding telemetry reception
- **Smart display switching**: Single button controls both ARM and display modes
- **Real-time data logging**: CSV output for flight analysis and tuning
- **Connection monitoring**: Visual feedback on telemetry packet drops
- **CRC validation**: Ensures telemetry data integrity
- **Frequency tracking**: Monitors telemetry update rate for performance tuning

## Contributing

This project maintains compatibility with the reference Arduino implementation while providing a clean PlatformIO structure for development and maintenance.

## License

This project is open source. See individual source files for specific license information.