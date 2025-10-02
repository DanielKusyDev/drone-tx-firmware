#pragma once

#include "protocol.h"
#include "control.h"

/**
 * @file Display.h
 * @brief OLED display management for transmitter UI
 * 
 * Provides different view modes for telemetry and debug information
 */

/**
 * @brief Update OLED when no telemetry is available (normal view)
 * @param inputs Current control inputs
 */
void updateOledNoTelemNormalView(const ControlInputs& inputs);

/**
 * @brief Update OLED when no telemetry is available (debug view)
 * @param inputs Current control inputs
 */
void updateOledNoTelemDebugView(const ControlInputs& inputs);

/**
 * @brief Update OLED with telemetry data (normal view)
 * @param inputs Current control inputs
 * @param telem Telemetry packet from drone
 * @param dropCount Number of dropped packets
 */
void updateOledNormalView(const ControlInputs& inputs, const TelemetryPacket& telem, uint32_t dropCount);

/**
 * @brief Update OLED with telemetry data (debug view)
 * @param inputs Current control inputs
 * @param telem Telemetry packet from drone
 * @param dropCount Number of dropped packets
 */
void updateOledDebugView(const ControlInputs& inputs, const TelemetryPacket& telem, uint32_t dropCount);