/*
 * Joe LCD - 20x4 I2C LCD Controller
 * Uses hd44780 library (auto-detects I2C backpack pin mapping)
 * 
 * Receives: say:line1|line2|line3|line4\n
 * Displays on 20x4 HD44780 LCD
 * 
 * Required library: hd44780 (install via Arduino Library Manager)
 */

#include <Wire.h>
#include <hd44780.h>
#include <hd44780ioClass/hd44780_I2Cexp.h>

hd44780_I2Cexp lcd;

const int LCD_COLS = 20;
const int LCD_ROWS = 4;

String inputBuffer = "";
bool dataReady = false;

void setup() {
  Serial.begin(9600);
  
  lcd.begin(LCD_COLS, LCD_ROWS);
  lcd.backlight();
  lcd.clear();
  
  lcd.setCursor(0, 0);
  lcd.print("Joe v1.0");
  lcd.setCursor(0, 1);
  lcd.print("Starting...");
  
  Serial.println("LCD READY");
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (inputBuffer.length() > 0) {
        dataReady = true;
        break;
      }
    } else {
      inputBuffer += c;
    }
  }
  
  if (dataReady) {
    processMessage(inputBuffer);
    inputBuffer = "";
    dataReady = false;
  }
}

void processMessage(String msg) {
  if (!msg.startsWith("say:")) {
    return;
  }
  
  String payload = msg.substring(4);
  
  String lines[4] = {"", "", "", ""};
  int lineIndex = 0;
  int startIdx = 0;
  
  for (unsigned int i = 0; i <= payload.length(); i++) {
    if (i == payload.length() || payload.charAt(i) == '|') {
      if (lineIndex < 4) {
        lines[lineIndex] = payload.substring(startIdx, i);
        if ((int)lines[lineIndex].length() > LCD_COLS) {
          lines[lineIndex] = lines[lineIndex].substring(0, LCD_COLS);
        }
      }
      lineIndex++;
      startIdx = i + 1;
    }
  }
  
  lcd.clear();
  for (int row = 0; row < LCD_ROWS; row++) {
    lcd.setCursor(0, row);
    String line = lines[row];
    for (int col = 0; col < LCD_COLS; col++) {
      if (col < (int)line.length()) {
        lcd.print(line.charAt(col));
      } else {
        lcd.print(' ');
      }
    }
  }
}
