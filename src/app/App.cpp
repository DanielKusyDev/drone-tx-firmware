#include "App.h"
#include "config.h"

// Forward declare existing globals to maintain compatibility
extern RadioManager radio;
extern ControlManager control;
extern unsigned long g_lastOledUpdateMs;

// Global app instance
App g_app;

bool App::init() {
    // For Phase 1: Just forward to existing global objects
    // This maintains identical initialization behavior
    m_control = &control;
    m_radio = &radio;
    m_lastOledUpdateMs = 0;
    
    return true; // All actual init handled by existing global setup()
}

void App::loop() {
    // For Phase 1: Forward to existing main loop logic
    // This is a placeholder that maintains existing behavior
    // Later phases will move actual logic here
}

void App::handleSerialCommands() {
    // Placeholder for Phase 1 - existing logic remains in main.cpp
}

void App::processControlInputs() {
    // Placeholder for Phase 1
}

void App::applySafetyLogic() {
    // Placeholder for Phase 1  
}

void App::buildAndSendRcPacket() {
    // Placeholder for Phase 1
}

void App::processTelemetry() {
    // Placeholder for Phase 1
}

void App::updateDisplay() {
    // Placeholder for Phase 1
}