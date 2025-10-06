import re
import matplotlib

matplotlib.use('TkAgg')  # Use TkAgg backend to avoid rendering issues
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import numpy as np

# Log data
log_data = open("flight_log.txt").read()
# Parse data
data = {
    'time': [],
    'roll': [], 'pitch': [], 'yaw': [],
    'setR': [], 'setP': [], 'setYR': [],
    'throttle': [],
    'motor0': [], 'motor1': [], 'motor2': [], 'motor3': [],
    'armed': []
}

time_idx = 0
current_state = {}

for line in log_data.split('\n'):
    if 'TEL: ATT:' in line:
        match = re.search(r'R=([-\d.]+) P=([-\d.]+) Y=([-\d.]+)', line)
        if match:
            current_state['roll'] = float(match.group(1))
            current_state['pitch'] = float(match.group(2))
            current_state['yaw'] = float(match.group(3))

    elif 'TEL: CTL:' in line:
        match = re.search(r'setR=([-\d.]+) setP=([-\d.]+) setYR=([-\d.]+)', line)
        if match:
            current_state['setR'] = float(match.group(1))
            current_state['setP'] = float(match.group(2))
            current_state['setYR'] = float(match.group(3))

    elif 'TEL: MOT:' in line:
        match = re.search(r'cmd=\[(\d+) (\d+) (\d+) (\d+)\].*THR=(\d+)', line)
        if match:
            current_state['motor0'] = int(match.group(1))
            current_state['motor1'] = int(match.group(2))
            current_state['motor2'] = int(match.group(3))
            current_state['motor3'] = int(match.group(4))
            current_state['throttle'] = int(match.group(5))

    elif 'TEL: STA:' in line:
        match = re.search(r'armed=(\d+)', line)
        if match:
            current_state['armed'] = int(match.group(1))

            # Record complete state
            if all(k in current_state for k in ['roll', 'pitch', 'throttle', 'armed']):
                data['time'].append(time_idx)
                data['roll'].append(current_state['roll'])
                data['pitch'].append(current_state['pitch'])
                data['yaw'].append(current_state.get('yaw', 0))
                data['setR'].append(current_state.get('setR', 0))
                data['setP'].append(current_state.get('setP', 0))
                data['setYR'].append(current_state.get('setYR', 0))
                data['throttle'].append(current_state['throttle'])
                data['motor0'].append(current_state.get('motor0', 0))
                data['motor1'].append(current_state.get('motor1', 0))
                data['motor2'].append(current_state.get('motor2', 0))
                data['motor3'].append(current_state.get('motor3', 0))
                data['armed'].append(current_state['armed'])
                time_idx += 1

# Create visualization
fig = plt.figure(figsize=(14, 10))
gs = GridSpec(4, 2, figure=fig, hspace=0.3, wspace=0.3)

# Attitude plot
ax1 = fig.add_subplot(gs[0, :])
ax1.plot(data['time'], data['roll'], 'r-', linewidth=2, label='Roll')
ax1.plot(data['time'], data['pitch'], 'b-', linewidth=2, label='Pitch')
ax1.plot(data['time'], data['yaw'], 'g-', linewidth=2, label='Yaw')
ax1.axhline(y=0, color='k', linestyle='--', alpha=0.3)
ax1.set_ylabel('Angle (degrees)', fontsize=10)
ax1.set_title('Aircraft Attitude (Roll/Pitch/Yaw)', fontsize=12, fontweight='bold')
ax1.legend(loc='upper left')
ax1.grid(True, alpha=0.3)

# Control inputs
ax2 = fig.add_subplot(gs[1, :])
ax2.plot(data['time'], data['setR'], 'r--', linewidth=1.5, label='Set Roll', alpha=0.7)
ax2.plot(data['time'], data['setP'], 'b--', linewidth=1.5, label='Set Pitch', alpha=0.7)
ax2.axhline(y=0, color='k', linestyle='--', alpha=0.3)
ax2.set_ylabel('Command (degrees)', fontsize=10)
ax2.set_title('Control Inputs (Pilot Commands)', fontsize=12, fontweight='bold')
ax2.legend(loc='upper left')
ax2.grid(True, alpha=0.3)

# Throttle
ax3 = fig.add_subplot(gs[2, :])
ax3.plot(data['time'], data['throttle'], 'purple', linewidth=2.5)
ax3.fill_between(data['time'], data['throttle'], alpha=0.3, color='purple')
ax3.set_ylabel('Throttle (%)', fontsize=10)
ax3.set_title('Throttle', fontsize=12, fontweight='bold')
ax3.grid(True, alpha=0.3)

# Motor outputs
ax4 = fig.add_subplot(gs[3, 0])
ax4.plot(data['time'], data['motor0'], label='M0', linewidth=1.5)
ax4.plot(data['time'], data['motor1'], label='M1', linewidth=1.5)
ax4.plot(data['time'], data['motor2'], label='M2', linewidth=1.5)
ax4.plot(data['time'], data['motor3'], label='M3', linewidth=1.5)
ax4.set_ylabel('Motor Command', fontsize=10)
ax4.set_xlabel('Sample Index', fontsize=10)
ax4.set_title('Individual Motor Commands', fontsize=12, fontweight='bold')
ax4.legend(loc='upper left', fontsize=8)
ax4.grid(True, alpha=0.3)

# Armed state
ax5 = fig.add_subplot(gs[3, 1])
ax5.fill_between(data['time'], data['armed'], step='post', alpha=0.5, color='red')
ax5.set_ylim([-0.1, 1.1])
ax5.set_ylabel('Armed State', fontsize=10)
ax5.set_xlabel('Sample Index', fontsize=10)
ax5.set_title('Armed Status (0=Disarmed, 1=Armed)', fontsize=12, fontweight='bold')
ax5.grid(True, alpha=0.3)

# Add crash annotation
crash_idx = None
for i, (r, p) in enumerate(zip(data['roll'], data['pitch'])):
    if abs(r) > 15 or abs(p) > 10:
        crash_idx = i
        break

if crash_idx:
    for ax in [ax1, ax2, ax3, ax4, ax5]:
        ax.axvline(x=data['time'][crash_idx], color='red', linestyle=':', linewidth=2, alpha=0.7, label='Crash point')

plt.suptitle('Flight Crash Analysis - Loss of Control Event', fontsize=14, fontweight='bold', y=0.995)
plt.tight_layout()
plt.show()
