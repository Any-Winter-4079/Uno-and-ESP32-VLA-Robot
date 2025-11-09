# Notes on the `esp32/` code:

The ESP32s (1x ESP32-WROVER and 2x ESP32-CAM) handle:

- image capturing
- incoming and outgoing audio processing
- command reception (from computer)

## Directory Structure

- `cam/` contains the production code for the 2x ESP32-CAM:
  - `aithinker-production.ino`
  - `m5stackwide-production.ino`
- `wrover/production.ino` contains the production code for the ESP32-WROVER

## ESP32 Setup

- Define in these lines your home WiFi' and phone hotspot's SSID and password:

```
const char* ssid1 = "";                     // Home WiFi SSID
const char* password1 = "";                 // Home WiFi password
```

```
const char* ssid2 = "";                     // Phone hotspot SSID
const char* password2 = "";                 // Phone hotspot password
```

- Define in these lines the IP, gateway and subnet for each ESP32-CAM and ESP32-WROVER, e.g.:

```
IPAddress staticIP1(192, 168, 1, 181);      // Static IP to request from home network
IPAddress gateway1(192, 168, 1, 1);         // Gateway for home network
IPAddress subnet1(255, 255, 255, 0);        // Subnet mask for home network

IPAddress staticIP2(172, 20, 10, 11);       // Static IP to request from the hotspot
IPAddress gateway2(172, 20, 10, 1);         // Gateway for hotspot
IPAddress subnet2(255, 255, 255, 0);        // Subnet mask for hotspot
```

- Define in these lines your computer's IP:

```
const char* websocket_server_host1 = "192.168.1.174"; // Static IP to request from home network

const char* websocket_server_host2 = "172.20.10.4";   // Static IP to request from hotspot
```

- Code upload requires either USB-C port or USB-to-serial adapter with:
  - FTDI 5V → ESP32-CAM 5V (FTDI set to 3.3V)
  - FTDI GND → ESP32-CAM GND
  - FTDI TXD → ESP32-CAM U0R
  - FTDI RXD → ESP32-CAM U0T
  - ESP32-CAM GND → ESP32-CAM IO0 (for flash mode)
- IO0 must be grounded during upload, then disconnected to run

## Network Configuration

- Dual network support (connect to either your phone hotspot or your home WiFi)
- For phone hotspot setup:
  1. Enable hotspot
  2. Enable "Maximize Compatibility"
  3. Power on robot
  4. Connect computer to hotspot

## Dependencies

Required libraries (to place in `Arduino/libraries/`):

- https://github.com/espressif/esp32-camera
- https://github.com/me-no-dev/AsyncTCP
- https://github.com/me-no-dev/ESPAsyncWebServer
- https://github.com/gilmaimon/ArduinoWebsockets

For example in:

```
Users/you/Documents/Arduino/libraries/esp32-camera-master
Users/you/Documents/Arduino/libraries/AsyncTCP
Users/you/Documents/Arduino/libraries/ESPAsyncWebServer-master
Users/you/Documents/Arduino/libraries/ArduinoWebsockets
```

## Credits

The AsyncBufferResponse, AsyncFrameResponse and sendJpg() code that (together with ESPAsyncWebServer) enabled **stable** (e.g., not out-of-order) images up to 37 fps is from:
https://gist.github.com/me-no-dev/d34fba51a8f059ac559bf62002e61aa3
