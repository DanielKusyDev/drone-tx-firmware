"""
Python Bridge CLI - Simple command-line interface for testing.

Usage:
    python cli.py listen --port COM3 --baudrate 115200
    python cli.py params list --port COM3
    python cli.py params get 0 --port COM3
    python cli.py params set 0 300.5 --port COM3
"""

import asyncio
import logging
import sys

import click

from app.config import settings
from app.services.unified_bridge import UnifiedBridge

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@click.group()
def cli():
    """Python Bridge CLI - Telemetry and PARAM communication."""
    pass


@cli.command()
@click.option(
    "--port",
    default=settings.telemetry_port,
    help="Serial port (e.g., COM3 or /dev/ttyUSB0)",
)
@click.option("--baudrate", default=settings.baudrate, help="Baud rate")
@click.option("--verbose", is_flag=True, help="Enable debug logging")
def listen(port: str, baudrate: int, verbose: bool):
    """
    Listen to telemetry stream and print packets.

    Press Ctrl+C to stop.
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    asyncio.run(_listen(port, baudrate))


async def _listen(port: str, baudrate: int):
    """Listen to telemetry and print packets."""
    click.echo(f"Connecting to {port} @ {baudrate} baud...")

    async def on_telemetry(packet):
        """Print telemetry packet."""
        pkt_type = packet.get("type")
        seq = packet.get("seq")

        if pkt_type == "ATT":
            click.echo(
                f"[ATT #{seq:04d}] Roll: {packet['roll_deg']:6.2f}° "
                f"Pitch: {packet['pitch_deg']:6.2f}° "
                f"Yaw: {packet['yaw_deg']:6.2f}°"
            )
        elif pkt_type == "MOT":
            motors = packet["motors"]
            click.echo(
                f"[MOT #{seq:04d}] Motors: {motors[0]:5d} {motors[1]:5d} {motors[2]:5d} {motors[3]:5d} "
                f"Throttle: {packet['throttle']:5d}"
            )
        elif pkt_type == "STA":
            armed = "ARMED" if packet["armed"] else "DISARMED"
            click.echo(
                f"[STA #{seq:04d}] {armed} | "
                f"Battery: {packet['battery_pct']:3d}% | "
                f"Link: {packet['link_quality']:3d}% | "
                f"Loop: {packet['loop_rate_hz']:6.1f} Hz"
            )
        else:
            # Print other packet types
            click.echo(f"[{pkt_type} #{seq:04d}] {packet}")

    bridge = UnifiedBridge(port, baudrate, settings.history_size, settings.param_timeout)
    bridge.set_telemetry_callback(on_telemetry)

    try:
        await bridge.start()
        click.echo("✅ Connected! Listening for telemetry... (Ctrl+C to stop)")

        # Keep running until Ctrl+C
        while True:
            await asyncio.sleep(1.0)

            # Print health every 10 seconds
            if int(asyncio.get_event_loop().time()) % 10 == 0:
                health = await bridge.get_health()
                age = health.get("last_packet_age_s")
                if age is not None:
                    click.echo(f"[HEALTH] Packets: {health['packets_received']} | Last: {age:.1f}s ago")

    except KeyboardInterrupt:
        click.echo("\n\nStopping...")
    finally:
        await bridge.stop()
        click.echo("✅ Disconnected")


@cli.group()
def params():
    """PARAM commands (list/get/set)."""
    pass


@params.command("list")
@click.option("--port", default=settings.telemetry_port, help="Serial port")
@click.option("--baudrate", default=settings.baudrate, help="Baud rate")
def params_list(port: str, baudrate: int):
    """List all parameters."""
    asyncio.run(_params_list(port, baudrate))


async def _params_list(port: str, baudrate: int):
    """List all parameters."""
    click.echo(f"Connecting to {port} @ {baudrate} baud...")

    bridge = UnifiedBridge(port, baudrate, settings.history_size, settings.param_timeout)

    try:
        await bridge.start()
        click.echo("Fetching parameter list...\n")

        params = await bridge.list_params()

        if not params:
            click.echo("No parameters found.")
            return

        # Print header
        click.echo(f"{'Index':>5} | {'Group':<16} | {'Name':<16} | {'Type':>4} | {'Access':>6} | {'Value':>10}")
        click.echo("-" * 80)

        # Print parameters
        for p in params:
            access = "RW" if p["param_access"] == 1 else "RO"
            click.echo(
                f"{p['index']:5d} | {p['group']:<16} | {p['name']:<16} | "
                f"{p['param_type']:4d} | {access:>6} | {p['value']:10.2f}"
            )

        click.echo(f"\nTotal: {len(params)} parameters")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)
    finally:
        await bridge.stop()


@params.command("get")
@click.argument("index", type=int)
@click.option("--port", default=settings.telemetry_port, help="Serial port")
@click.option("--baudrate", default=settings.baudrate, help="Baud rate")
def params_get(index: int, port: str, baudrate: int):
    """Get parameter value by index."""
    asyncio.run(_params_get(index, port, baudrate))


async def _params_get(index: int, port: str, baudrate: int):
    """Get parameter value."""
    click.echo(f"Connecting to {port} @ {baudrate} baud...")

    bridge = UnifiedBridge(port, baudrate, settings.history_size, settings.param_timeout)

    try:
        await bridge.start()

        value = await bridge.get_param(index)
        click.echo(f"Parameter[{index}] = {value:.2f}")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)
    finally:
        await bridge.stop()


@params.command("set")
@click.argument("index", type=int)
@click.argument("value", type=float)
@click.option("--port", default=settings.telemetry_port, help="Serial port")
@click.option("--baudrate", default=settings.baudrate, help="Baud rate")
def params_set(index: int, value: float, port: str, baudrate: int):
    """Set parameter value by index."""
    asyncio.run(_params_set(index, value, port, baudrate))


async def _params_set(index: int, value: float, port: str, baudrate: int):
    """Set parameter value."""
    click.echo(f"Connecting to {port} @ {baudrate} baud...")

    bridge = UnifiedBridge(port, baudrate, settings.history_size, settings.param_timeout)

    try:
        await bridge.start()

        await bridge.set_param(index, value)
        click.echo(f"✅ Parameter[{index}] set to {value:.2f}")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)
    finally:
        await bridge.stop()


@cli.command()
def ports():
    """List available serial ports."""
    from app.core.serial_connection import SerialConnection

    ports = SerialConnection.list_ports()

    if not ports:
        click.echo("No serial ports found.")
        return

    click.echo("Available serial ports:\n")
    for port in ports:
        click.echo(f"  {port['device']}")
        click.echo(f"    Description: {port['description']}")
        click.echo(f"    HWID: {port['hwid']}\n")


if __name__ == "__main__":
    cli()
