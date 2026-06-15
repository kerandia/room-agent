"""
LCD Self-Test - Tests 20x4 LCD independently from the agent.
Sends test patterns to verify rows are correct and aligned.

Usage: python lcd_selftest.py [PORT]
Example: python lcd_selftest.py COM5
"""

import sys
import time
import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM5"
BAUD = 9600

def send_lcd(ser, line1, line2, line3, line4):
    """Send 4 lines to LCD via serial"""
    msg = f"say:{line1}|{line2}|{line3}|{line4}\n"
    ser.write(msg.encode())
    print(f"Sent: {msg.strip()}")

def main():
    print(f"Connecting to {PORT} at {BAUD} baud...")
    try:
        ser = serial.Serial(PORT, BAUD, timeout=2)
        time.sleep(2)  # Wait for Arduino reset
        print("Connected!")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # Test 1: Row identification
    print("\n=== TEST 1: Row Identification ===")
    send_lcd(ser, "11111111111111111111", "22222222222222222222",
             "33333333333333333333", "44444444444444444444")
    input("Look at the LCD. Are rows 1/2/3/4 in order top-to-bottom? Press Enter...")

    # Test 2: Character set
    print("\n=== TEST 2: Character Set ===")
    send_lcd(ser, "ABCDEFGHJKLMNPQRT", "UVWXYZ0123456789",
             "/|_-.*+={}[]<>!@", "   Joe v1.0  OK!   ")
    input("Look at the LCD. Are all characters readable? Press Enter...")

    # Test 3: Alignment
    print("\n=== TEST 3: Center Alignment ===")
    send_lcd(ser,              "       HELLO       ", "     WORLD!        ",
             "    Joe is alive!   ", "   20x4 LCD Test   ")
    input("Look at the LCD. Is text centered? Press Enter...")

    # Test 4: Edge cases
    print("\n=== TEST 4: Edge Cases ===")
    send_lcd(ser, "<20 chars>          ", "x",
             "                    ", "FULL LINE PADDING!!")
    input("Look at the LCD. Edges aligned? Press Enter...")

    print("\n=== ALL TESTS DONE ===")
    print("If all tests look good, the firmware is fine.")
    print("If rows are scrambled, check ROW_ADDR in the .ino sketch.")
    print("If characters garbled, check I2C address (0x27 vs 0x3F).")
    
    ser.close()

if __name__ == "__main__":
    main()
