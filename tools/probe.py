"""Diagnostic CLI: probe an RPLIDAR over serial and report what happens
at each step. Intended for hardware debugging."""
from __future__ import annotations

import argparse
import sys
import time
import traceback

import serial
from pyrplidar import PyRPlidar


def hexdump(label: str, data: bytes, max_bytes: int = 64) -> None:
    snippet = data[:max_bytes]
    hex_str = " ".join(f"{b:02x}" for b in snippet)
    extra = f" (+{len(data) - max_bytes} more)" if len(data) > max_bytes else ""
    print(f"[hex] {label} len={len(data)}: {hex_str}{extra}")


def raw_scan_test(port: str, baudrate: int, dtr_low: bool = True, motor_pwm: int | None = None) -> None:
    """Bypass pyrplidar entirely: connect, optionally drive DTR + motor PWM, send SCAN, dump measurements."""
    print(f"\n=== RAW SCAN TEST: dtr_low={dtr_low} motor_pwm={motor_pwm} ===")
    import struct as _struct
    s = serial.Serial(port, baudrate, timeout=1, dsrdtr=False)
    try:
        # Settle
        s.write(b"\xA5\x25")  # STOP
        time.sleep(0.05)
        s.reset_input_buffer()

        # Drive DTR
        s.dtr = (not dtr_low)  # dtr=False means line is low
        time.sleep(0.05)

        # Optional motor PWM
        if motor_pwm is not None:
            payload = _struct.pack("<H", motor_pwm)
            s.write(b"\xA5\xF0" + bytes([len(payload)]) + payload + bytes([(0xA5 ^ 0xF0 ^ len(payload) ^ payload[0] ^ payload[1]) & 0xFF]))
            time.sleep(0.05)
            s.reset_input_buffer()

        print("[..] sleeping 1.5s for motor spinup")
        time.sleep(1.5)

        # SCAN command (0xA5 0x20)
        s.reset_input_buffer()
        s.write(b"\xA5\x20")

        # Read descriptor
        descr = s.read(7)
        hexdump("SCAN descriptor", descr)
        if len(descr) < 7:
            print("[err] short descriptor — device not responding")
            return
        if descr[0] != 0xA5 or descr[1] != 0x5A:
            print("[err] sync mismatch on SCAN descriptor")
            return

        # Read 20 measurements (5 bytes each)
        print("[..] reading 20 raw 5-byte measurements")
        good = 0
        for i in range(20):
            data = s.read(5)
            if len(data) < 5:
                print(f"  #{i:02d} SHORT read {len(data)} bytes: {data.hex()}")
                continue
            quality = data[0] >> 2
            start_flag = bool(data[0] & 1)
            angle = ((data[1] >> 1) + (data[2] << 7)) / 64.0
            distance = (data[3] + (data[4] << 8)) / 4.0
            print(f"  #{i:02d} start={start_flag} q={quality:2d} angle={angle:6.2f}° dist={distance:7.1f}mm raw={data.hex()}")
            good += 1
        print(f"[summary] {good}/20 valid measurements")

        # STOP + motor off
        s.write(b"\xA5\x25")
        time.sleep(0.05)
        if motor_pwm is not None:
            zero = _struct.pack("<H", 0)
            s.write(b"\xA5\xF0" + bytes([len(zero)]) + zero + bytes([(0xA5 ^ 0xF0 ^ len(zero) ^ zero[0] ^ zero[1]) & 0xFF]))
        s.dtr = True  # release
    finally:
        s.close()


def raw_serial_test(port: str, baudrate: int) -> None:
    print(f"\n=== RAW SERIAL TEST: {port} @ {baudrate} ===")
    s = serial.Serial(port, baudrate, timeout=1)
    try:
        # Reset device (STOP command)
        s.write(b"\xA5\x25")
        time.sleep(0.05)
        s.reset_input_buffer()

        # GET_HEALTH (0xA5 0x52)
        s.write(b"\xA5\x52")
        descr = s.read(7)
        hexdump("HEALTH descriptor", descr)
        if len(descr) >= 7 and descr[0] == 0xA5 and descr[1] == 0x5A:
            payload = s.read(3)
            hexdump("HEALTH payload", payload)
            if len(payload) == 3:
                print(f"  health.status={payload[0]} error={payload[1] | (payload[2] << 8)}")

        time.sleep(0.05)
        s.reset_input_buffer()

        # GET_INFO (0xA5 0x50)
        s.write(b"\xA5\x50")
        descr = s.read(7)
        hexdump("INFO descriptor", descr)
        if len(descr) >= 7 and descr[0] == 0xA5 and descr[1] == 0x5A:
            payload = s.read(20)
            hexdump("INFO payload", payload)
            if len(payload) >= 4:
                print(f"  model=0x{payload[0]:02x} fw={payload[2]}.{payload[1]} hw={payload[3]}")
    finally:
        s.close()


def pyrplidar_test(port: str, baudrate: int, motor_pwm: int, spinup_s: float) -> None:
    print(f"\n=== PYRPLIDAR TEST: {port} @ {baudrate} ===")
    lidar = PyRPlidar()
    try:
        lidar.connect(port=port, baudrate=baudrate, timeout=1)
        print("[ok] connected")

        try:
            info = lidar.get_info()
            print(f"[ok] info: model={info.model} fw={info.firmware_major}.{info.firmware_minor} hw={info.hardware}")
        except Exception as exc:
            print(f"[err] get_info: {exc!r}")
            traceback.print_exc()

        try:
            health = lidar.get_health()
            print(f"[ok] health: status={health.status} error_code={health.error_code}")
        except Exception as exc:
            print(f"[err] get_health: {exc!r}")
            traceback.print_exc()

        # Settle + flush
        try:
            lidar.stop()
        except Exception as exc:
            print(f"[warn] stop before scan: {exc!r}")
        time.sleep(0.1)
        try:
            lidar.lidar_serial._serial.reset_input_buffer()
        except Exception as exc:
            print(f"[warn] reset_input_buffer: {exc!r}")

        # Motor spinup
        print(f"[..] set_motor_pwm({motor_pwm})")
        try:
            lidar.set_motor_pwm(motor_pwm)
        except Exception as exc:
            print(f"[err] set_motor_pwm: {exc!r}")
            traceback.print_exc()
        time.sleep(spinup_s)
        try:
            lidar.lidar_serial._serial.reset_input_buffer()
        except Exception:
            pass

        # Start scan
        print("[..] start_scan()")
        try:
            scan_gen = lidar.start_scan()
        except Exception as exc:
            print(f"[err] start_scan: {exc!r}")
            traceback.print_exc()
            return

        # Pull N measurements
        N = 20
        print(f"[..] reading first {N} measurements")
        try:
            gen = scan_gen()
            for i, m in enumerate(gen):
                print(f"  #{i:02d} start_flag={m.start_flag} quality={m.quality} angle={m.angle:.2f}° dist={m.distance:.1f}mm")
                if i + 1 >= N:
                    break
            print("[ok] received measurements")
        except Exception as exc:
            print(f"[err] reading scan_gen: {exc!r}")
            traceback.print_exc()
        finally:
            try:
                lidar.stop()
            except Exception:
                pass
            try:
                lidar.set_motor_pwm(0)
            except Exception:
                pass
    finally:
        try:
            lidar.disconnect()
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="/dev/cu.usbserial-1410")
    parser.add_argument("--baudrate", type=int, default=460800)
    parser.add_argument("--motor-pwm", type=int, default=660)
    parser.add_argument("--spinup", type=float, default=1.5)
    parser.add_argument("--skip-raw", action="store_true")
    args = parser.parse_args()

    if not args.skip_raw:
        try:
            raw_serial_test(args.port, args.baudrate)
        except Exception as exc:
            print(f"[err] raw test: {exc!r}")
            traceback.print_exc()

        # Raw scan, no motor PWM (C1 might auto-spin with DTR low).
        try:
            raw_scan_test(args.port, args.baudrate, dtr_low=True, motor_pwm=None)
        except Exception as exc:
            print(f"[err] raw scan no-pwm: {exc!r}")
            traceback.print_exc()

        # Raw scan, with motor PWM.
        try:
            raw_scan_test(args.port, args.baudrate, dtr_low=True, motor_pwm=args.motor_pwm)
        except Exception as exc:
            print(f"[err] raw scan pwm: {exc!r}")
            traceback.print_exc()

    pyrplidar_test(args.port, args.baudrate, args.motor_pwm, args.spinup)
    return 0


if __name__ == "__main__":
    sys.exit(main())
