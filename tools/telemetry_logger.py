#!/usr/bin/env python3
"""
RC Transmitter Telemetry Logger
Zapisuje dane telemetryczne z nadajnika do pliku CSV
"""

import serial
import csv
import time
from datetime import datetime
import os
import sys

def find_serial_ports():
    """Znajdź dostępne porty szeregowe"""
    import serial.tools.list_ports
    ports = list(serial.tools.list_ports.comports())
    return [(port.device, port.description) for port in ports]

def main():
    print("🛸 RC Transmitter Telemetry Logger")
    print("=" * 40)
    
    # Pokaż dostępne porty
    ports = find_serial_ports()
    if not ports:
        print("❌ Nie znaleziono portów szeregowych!")
        return
    
    print("📡 Dostępne porty:")
    for i, (port, desc) in enumerate(ports):
        print(f"  {i+1}. {port} - {desc}")
    
    # Wybór portu
    try:
        choice = int(input(f"\n🔌 Wybierz port (1-{len(ports)}): ")) - 1
        if choice < 0 or choice >= len(ports):
            raise ValueError("Nieprawidłowy wybór")
        selected_port = ports[choice][0]
    except (ValueError, IndexError):
        print("❌ Nieprawidłowy wybór portu!")
        return
    
    # Nazwa pliku z timestampem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"telemetry_log_{timestamp}.csv"
    filepath = os.path.join(os.path.dirname(__file__), "..", "logs", filename)
    
    # Utwórz katalog logs jeśli nie istnieje
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    print(f"💾 Zapisywanie do: {filename}")
    print(f"🚀 Podłączanie do {selected_port} (115200 baud)...")
    
    try:
        # Otwórz port szeregowy
        ser = serial.Serial(selected_port, 115200, timeout=1)
        time.sleep(2)  # Poczekaj na stabilizację połączenia
        
        print("✅ Połączono! Oczekiwanie na dane telemetryczne...")
        print("📊 Naciśnij Ctrl+C aby zatrzymać nagrywanie")
        print("-" * 60)
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = None
            packet_count = 0
            start_time = time.time()
            
            while True:
                try:
                    line = ser.readline().decode('utf-8').strip()
                    
                    if not line:
                        continue
                    
                    # Pomiń linie które nie są danymi CSV
                    if not line.replace(',', '').replace('.', '').replace('-', '').replace(' ', '').isdigit():
                        if "ms,armed" in line:  # To jest nagłówek
                            print(f"📋 Znaleziono nagłówek CSV: {line}")
                            if writer is None:
                                # Pierwszy nagłówek - utwórz writer
                                headers = line.split(',')
                                writer = csv.writer(csvfile)
                                writer.writerow(headers)
                                csvfile.flush()
                        continue
                    
                    if writer is None:
                        print("⚠️  Oczekiwanie na nagłówek CSV...")
                        continue
                    
                    # Zapisz dane
                    data = line.split(',')
                    writer.writerow(data)
                    csvfile.flush()
                    
                    packet_count += 1
                    
                    # Pokaż postęp co 50 pakietów
                    if packet_count % 50 == 0:
                        elapsed = time.time() - start_time
                        rate = packet_count / elapsed if elapsed > 0 else 0
                        print(f"📈 Pakietów: {packet_count:4d} | Czas: {elapsed:6.1f}s | Częstotliwość: {rate:4.1f} Hz")
                    
                except UnicodeDecodeError:
                    continue  # Pomiń uszkodzone dane
                    
    except serial.SerialException as e:
        print(f"❌ Błąd portu szeregowego: {e}")
        return
    except KeyboardInterrupt:
        print(f"\n🛑 Zatrzymano przez użytkownika")
        if 'packet_count' in locals():
            elapsed = time.time() - start_time
            rate = packet_count / elapsed if elapsed > 0 else 0
            print(f"📊 Zapisano łącznie: {packet_count} pakietów w {elapsed:.1f}s ({rate:.1f} Hz)")
        print(f"💾 Dane zapisane w: {filepath}")
    except Exception as e:
        print(f"❌ Niespodziewany błąd: {e}")
    finally:
        if 'ser' in locals():
            ser.close()

if __name__ == "__main__":
    main()