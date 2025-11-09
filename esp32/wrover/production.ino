// #################################################################################
// Production sketch for ESP32-WROVER to send audio and receive audio and commands #
// #################################################################################

// takes care of ESP32-WROVER - computer WiFi connection
#include <WiFi.h>
// takes care of asynchronous TCP connections for the server
#include <AsyncTCP.h>
// takes care of I2S audio for microphone and speaker
#include <driver/i2s.h>
// takes care of mutex for thread-safe audio buffering
#include <freertos/semphr.h>
// takes care of the asynchronous HTTP server
#include <ESPAsyncWebServer.h>
// takes care of the WebSocket client
#include <ArduinoWebsockets.h>
// takes care of FreeRTOS primitives (tasks, delays, scheduling)
#include <freertos/FreeRTOS.h>

// ###############
// Configuration #
// ###############

// UART2 to forward commands to the Uno (for the motors through the L298N and for the SG90s)
// UART2 is a software-configurable UART (Universal Asynchronous Receiver/Transmitter)
HardwareSerial mySerial(2);

// I2S buffers
#define bufferCnt 10                                    // Number of I2S DMA (Direct Memory Access) buffers
#define bufferLen 1024                                  // Size of each I2S DMA buffer (in number of positions)

// INMP441 microphone pins & port
#define INMP441_SD 26                                   // I2S Serial Data
#define INMP441_WS 19                                   // I2S Word Select
#define INMP441_SCK 18                                  // I2S Serial Clock
#define INMP441_PORT I2S_NUM_0

// MAX98357A amplifier pins & port
#define MAX98357A_BCLK 14                               // I2S Bit Clock
#define MAX98357A_LRC 12                                // I2S Word Select / Left/Right Clock
#define MAX98357A_DIN 25                                // I2S Data Input
#define MAX98357A_SD 21                                 // I2S Shutdown
#define MAX98357A_PORT I2S_NUM_1

// End of audio signal
#define END_OF_AUDIO_SIGNAL "END_OF_AUDIO"

// INMP441 microphone buffer
int16_t listeningBuffer[bufferLen];

// MAX98357A amplifier buffer
#define SPEAKING_BUFFER_SIZE 32768                      // for 16K samples of 16-bit PCM
uint8_t speakingBuffer[SPEAKING_BUFFER_SIZE];
size_t speakingBufferIndex = 0;

// KY-037 sound detector
#define KY037_PIN 15

// Control volatile variables
volatile bool isSpeaking = false;                       // to indicate if speech (audio playback) is in progress
volatile bool soundDetected = false;                    // to indicate if KY-037 is detecting sound
volatile bool allowRecording = true;                    // to indicate if recording is allowed (after robot speaks or after it stays quiet)
volatile bool stopRecordingUponSameTranscript = false;  // to indicate if INMP441 is sending audio resulting in same transcript

// Control constant variables
const unsigned long MAX_RECORDING_DURATION_MS = 30000;  // to define the maximum duration of (listening) audio sent in one go

// Semaphore for thread-safe access to the speaking buffer
SemaphoreHandle_t speakingBufferSemaphore = NULL;

// Primary network configuration (home WiFi)
const char* ssid1 = "";                                 // Home WiFi SSID
const char* password1 = "";                             // Home WiFi password
IPAddress staticIP1(192, 168, 1, 182);                  // Static IP for home network
IPAddress gateway1(192, 168, 1, 1);                     // Gateway for home network
IPAddress subnet1(255, 255, 255, 0);                    // Subnet mask for home network
const char* websocket_server_host1 = "192.168.1.174";   // Computer IP

// Secondary network configuration (phone hotspot)
const char* ssid2 = "";                                 // Phone hotspot SSID
const char* password2 = "";                             // Phone hotspot password
IPAddress staticIP2(172, 20, 10, 12);                   // Static IP for hotspot
IPAddress gateway2(172, 20, 10, 1);                     // Gateway for hotspot
IPAddress subnet2(255, 255, 255, 0);                    // Subnet mask for hotspot
const char* websocket_server_host2 = "172.20.10.4";     // Computer IP

// WebSocket
char websocket_server_host[16];                         // Computer IP
const uint16_t websocket_server_port = 8888;            // Computer port
using namespace websockets;
WebsocketsClient client;
bool isWebSocketConnected;

// AsyncWebServer on port 80
AsyncWebServer server(80);                              // to receive commands from computer

// #####################################################
// Helper 1: Install I2S driver for INMP441 microphone #
// #####################################################
void inmp441_i2s_install() {
    const i2s_config_t i2s_config = {
        .mode = i2s_mode_t(I2S_MODE_MASTER | I2S_MODE_RX),
        .sample_rate = 16000, // for Whisper
        .bits_per_sample = i2s_bits_per_sample_t(16),
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
        .communication_format = i2s_comm_format_t(I2S_COMM_FORMAT_STAND_I2S),
        .intr_alloc_flags = 0,
        .dma_buf_count = bufferCnt,
        .dma_buf_len = bufferLen,
        .use_apll = false
    };
    i2s_driver_install(INMP441_PORT, &i2s_config, 0, NULL);
}

// ##############################################
// Helper 2: Assign pins for INMP441 microphone #
// ##############################################
void inmp441_i2s_setpin() {
    const i2s_pin_config_t pin_config = {
        .bck_io_num = INMP441_SCK,
        .ws_io_num = INMP441_WS,
        .data_out_num = -1,
        .data_in_num = INMP441_SD
    };
    i2s_set_pin(INMP441_PORT, &pin_config);
}

// ######################################################
// Helper 3: Install I2S driver for MAX98357A amplifier #
// ######################################################
void max98357a_i2s_install() {
    const i2s_config_t i2s_config = {
        .mode = i2s_mode_t(I2S_MODE_MASTER | I2S_MODE_TX),
        .sample_rate = 16000,
        .bits_per_sample = i2s_bits_per_sample_t(16),
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
        .communication_format = i2s_comm_format_t(I2S_COMM_FORMAT_STAND_I2S),
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = bufferCnt,
        .dma_buf_len = bufferLen,
        .use_apll = false
    };
    i2s_driver_install(MAX98357A_PORT, &i2s_config, 0, NULL);
}

// ###############################################
// Helper 4: Assign pins for MAX98357A amplifier #
// ###############################################
void max98357a_i2s_setpin() {
    const i2s_pin_config_t pin_config = {
        .bck_io_num = MAX98357A_BCLK,
        .ws_io_num = MAX98357A_LRC,
        .data_out_num = MAX98357A_DIN,
        .data_in_num = I2S_PIN_NO_CHANGE
    };
    i2s_set_pin(MAX98357A_PORT, &pin_config);
}

// ################################################################################################
// Helper 5: Interrupt handler after KY-037 has detected a sound to potentially set soundDetected #
// ################################################################################################
void IRAM_ATTR handleSoundDetection() {
    if (allowRecording) {
        soundDetected = true;
    }
}

// ##########################################################
// Helper 6: attempt to connect to (specified) WiFi network #
// ##########################################################
const char* connectToWiFi(const char* ssid, const char* password, IPAddress staticIP, IPAddress gateway, IPAddress subnet) {
    Serial.print("Connecting to ");
    Serial.println(ssid);

    WiFi.config(staticIP, gateway, subnet);
    WiFi.begin(ssid, password);

    // try for 10 seconds
    for (int i = 0; i < 10; i++) {
        if (WiFi.status() == WL_CONNECTED) {
            Serial.println("Connected!");
            Serial.print("IP address: ");
            Serial.println(WiFi.localIP());

            mySerial.print("SSID:");
            mySerial.println(ssid);
            return ssid;
        }
        delay(1000);
        Serial.print(".");
    }
    Serial.println("Connection failed.");
    return nullptr;
}

// ######################################################################
// Helper 7: attempt to connect to the WebSocket server on the computer #
// ######################################################################
void connectWSServer() {
    client.onEvent(onEventsCallback);
    client.onMessage(&onMessageCallback);
    int attempt = 0;
    const int max_attempts = 5;
    while (!client.connect(websocket_server_host, websocket_server_port, "/") && attempt < max_attempts) {
        delay(500);
        Serial.print(".");
        attempt++;
    }
    if (attempt < max_attempts) {
        Serial.println("Websocket Connected!");
    } else {
        Serial.println("Failed to connect to Websocket.");
    }
}

// ######################################################################
// Helper 8: receive and forward control instructions to Uno over UART2 #
// ######################################################################
void handleCommand(AsyncWebServerRequest *request) {
    if (request->method() == HTTP_POST) {
        String command = "";
        
        // left motor direction (10, 01, 00)
        if (request->hasParam("leftMD", true)) {
            Serial.print("leftMD:" + request->getParam("leftMD", true)->value());
            command += "leftMD:" + request->getParam("leftMD", true)->value() + ",";
        }
        // right motor direction (10, 01, 00)
        if (request->hasParam("rightMD", true)) {
            Serial.print("rightMD:" + request->getParam("rightMD", true)->value());
            command += "rightMD:" + request->getParam("rightMD", true)->value() + ",";
        }
        // motors speed (0-255)
        if (request->hasParam("motorsS", true)) {
            Serial.print("motorsS:" + request->getParam("motorsS", true)->value());
            command += "motorsS:" + request->getParam("motorsS", true)->value() + ",";
        }
        // angle vertical position (50, 110)
        if (request->hasParam("angleVP", true)) {
            Serial.print("angleVP:" + request->getParam("angleVP", true)->value());
            command += "angleVP:" + request->getParam("angleVP", true)->value() + ",";
        }
        // angle horizontal position (60, 120)
        if (request->hasParam("angleHP", true)) {
            Serial.print("angleHP:" + request->getParam("angleHP", true)->value());
            command += "angleHP:" + request->getParam("angleHP", true)->value();
        }
        
        // send command to Uno via UART2
        if (command != "") {
            mySerial.println(command);
            request->send(200, "text/plain", "Received command: " + command);
        } else {
            request->send(400, "text/plain", "Parameters are missing");
        }
    } else {
        request->send(405, "text/plain", "Method Not Allowed");
    }
}

// ###########################################################################################
// Helper 9: receive stop recording command for microphoneTask to stop sending INMP441 audio #
// ###########################################################################################
void handleStopRecordingUponSameTranscript(AsyncWebServerRequest *request) {
    if (request->method() == HTTP_POST) {
        if (request->hasParam("stop", true)) {
            String stopValue = request->getParam("stop", true)->value();
            if (stopValue == "true") {
                stopRecordingUponSameTranscript = true;
                Serial.println("Received stop recording command via HTTP");
                request->send(200, "text/plain", "Stop recording command received");
            } else {
                request->send(400, "text/plain", "Invalid stop value");
            }
        } else {
            request->send(400, "text/plain", "Missing 'stop' parameter");
        }
    } else {
        request->send(405, "text/plain", "Method Not Allowed");
    }
}

// ###########################################################################################################################
// Helper 10: receive allow recording command if robot stays quiet to allow KY-037 interrupt handler to update soundDetected #
// ###########################################################################################################################
void handleAllowRecordingWhenRobotThinksAndStaysQuiet(AsyncWebServerRequest *request) {
    if (request->method() == HTTP_POST) {
        if (request->hasParam("allow", true)) {
            String allowValue = request->getParam("allow", true)->value();
            if (allowValue == "true") {
                allowRecording = true;
                Serial.println("AllowRecording manually re-enabled via HTTP");
                request->send(200, "text/plain", "AllowRecording set to true");
            } else {
                request->send(400, "text/plain", "Invalid allow value");
            }
        } else {
            request->send(400, "text/plain", "Missing 'allow' parameter");
        }
    } else {
        request->send(405, "text/plain", "Method Not Allowed");
    }
}

// ############################################
// Helper 11: default WebSocket event handler #
// ############################################
void onEventsCallback(WebsocketsEvent event, String data) {
    if (event == WebsocketsEvent::ConnectionOpened) {
        Serial.println("Connection Opened");
        isWebSocketConnected = true;
    } else if (event == WebsocketsEvent::ConnectionClosed) {
        Serial.println("Connection Closed");
        isWebSocketConnected = false;
    } else if (event == WebsocketsEvent::GotPing) {
        Serial.println("Got a Ping!");
    } else if (event == WebsocketsEvent::GotPong) {
        Serial.println("Got a Pong!");
    }
}

// ###############################################################################
// Helper 12: (WebSocket message handler) handle incoming audio and END_OF_AUDIO #
// ###############################################################################
void onMessageCallback(WebsocketsMessage message) {
    if(message.isBinary()) {
        if(speakingBufferIndex == 0) {
            mySerial.println("Speaking...");
            // power up amplifier
            startAudio();
        }
        processAudioChunk((const uint8_t*)message.c_str(), message.length());
    } else if(message.isText()) {
        Serial.print("Received text: ");
        Serial.println(message.data());
        if(message.data() == END_OF_AUDIO_SIGNAL) {
            // wait for any remaining audio to finish playing
            // This feels unsafe, though:
            // what if speakingBuffer would overflow,
            // and playAudio is called.
            // Then speakingBufferIndex == 0 momentarily
            // but more audio is in need of playing
            while (speakingBufferIndex > 0) {
                vTaskDelay(pdMS_TO_TICKS(10));
            }
            // stop speaking (audio) and power down amplifier
            stopAudio();

            // add a slight (non-blocking) delay before allowing new recording
            xTaskCreate([](void*){
                vTaskDelay(pdMS_TO_TICKS(500));         // 500 ms delay
                allowRecording = true;                  // allow recording after not listening to yourself
                mySerial.println("Watching...");        // we have stopped speaking, and it's not clear the KY-037 will trigger so we shouldn't assume 'Listening'
                vTaskDelete(NULL);                      // clean up the task
            }, "reenableRecording", 2048, NULL, 1, NULL);
        }
    }
}

// #############################################################################################
// Helper 13: copy incoming audio chunk into buffer (playing audio if needed to clear buffer)  #
// #############################################################################################
void processAudioChunk(const uint8_t* data, size_t length) {
    bool wouldOverflow = false;

    if (xSemaphoreTake(speakingBufferSemaphore, portMAX_DELAY) == pdTRUE) {
        if (speakingBufferIndex + length > SPEAKING_BUFFER_SIZE) {
            wouldOverflow = true;
        } else {
            memcpy(speakingBuffer + speakingBufferIndex, data, length);
            speakingBufferIndex += length;
        }
        xSemaphoreGive(speakingBufferSemaphore);
    }

    if (wouldOverflow) {
        playAudio();    // if we would overflow, make space for the new data by playing the existing audio
                        // playAudio() runs while processAudioChunk() does not hold the mutex.
                        // Otherwise we would create a deadlock where playAudio() waits for the mutex 
                        // and processAudioChunk() for playAudio() to finish

        // once the buffer is free to be used from the very start,
        // write new audio while holding the mutex
        if (xSemaphoreTake(speakingBufferSemaphore, portMAX_DELAY) == pdTRUE) {
            speakingBufferIndex = 0;
            memcpy(speakingBuffer, data, length);
            speakingBufferIndex = length;
            xSemaphoreGive(speakingBufferSemaphore);
        }
    }
}

// ###################################################################
// Helper 14: play audio from buffer through the MAX98357A amplifier #
// ###################################################################
void playAudio() {
    if (xSemaphoreTake(speakingBufferSemaphore, portMAX_DELAY) == pdTRUE) {
        if (speakingBufferIndex > 0 && !isSpeaking) {
            isSpeaking = true;
            // enable the amplifier
            digitalWrite(MAX98357A_SD, HIGH);

            // lower the volume to 50%
            for (size_t i = 0; i < speakingBufferIndex; i += 2) {
                int16_t sample = ((int16_t*)speakingBuffer)[i/2];
                sample = sample / 2;  // / 2 for 50% reduction
                ((int16_t*)speakingBuffer)[i/2] = sample;
            }
            
            size_t bytesWritten = 0;
            esp_err_t result = i2s_write(MAX98357A_PORT, speakingBuffer, speakingBufferIndex, &bytesWritten, portMAX_DELAY);
            if (result != ESP_OK) {
                Serial.printf("Error writing to I2S: %d\n", result);
            } else {
                Serial.printf("Wrote %d bytes to I2S\n", bytesWritten);
            }
            
            speakingBufferIndex = 0;
            isSpeaking = false;
        }
        xSemaphoreGive(speakingBufferSemaphore);
    }
}

// #########################################################
// Helper 15: start I2S and enable the MAX98357A amplifier #
// #########################################################
void startAudio() {
    digitalWrite(MAX98357A_SD, HIGH);
    i2s_start(MAX98357A_PORT);
}

// ############################################################################
// Helper 16: stop I2S and send silence to power down the MAX98357A amplifier #
// ############################################################################
 void stopAudio() {
    // short period of silence
    const size_t silenceLength = 1024;
    uint8_t silence[silenceLength] = {0};
    size_t bytesWritten = 0;
    i2s_write(
        MAX98357A_PORT,
        silence,
        silenceLength,
        &bytesWritten,
        portMAX_DELAY
    );
    i2s_stop(MAX98357A_PORT);
    digitalWrite(MAX98357A_SD, LOW);
}

// ########################################################################################
// xTaskCreatePinnedToCore #1: handle audio capturing and streaming (for robot listening) #
// ########################################################################################
void microphoneTask(void* parameter) {
    size_t bytesIn = 0;
    while (1) {
        // connect to Wi-Fi if disconnected
        if (WiFi.status() != WL_CONNECTED) {
            connectToWiFi(ssid2, password2, staticIP2, gateway2, subnet2);
            if (WiFi.status() != WL_CONNECTED) {
                connectToWiFi(ssid1, password1, staticIP1, gateway1, subnet1);
            }
        }

        // connect to WebSocket if disconnected while idle
        if (!isWebSocketConnected) {
            Serial.println("WebSocket disconnected while idle — attempting reconnect...");
            connectWSServer();
        }

        if (soundDetected) {
            Serial.println("Sound detected. Recording...");
            if (!isWebSocketConnected) {
                connectWSServer();
            }

            size_t bytesIn = 0;
            int lastElapsedSecond = -1;
            unsigned long startTime = millis();
            int recordingDurationS = MAX_RECORDING_DURATION_MS / 1000;
            
            while (millis() - startTime < MAX_RECORDING_DURATION_MS) {
                if (stopRecordingUponSameTranscript) {
                    soundDetected = false;
                    allowRecording = false;
                    Serial.println("Stopping recording...");
                    break;
                }
                if (!isWebSocketConnected) {
                    connectWSServer();
                }
                int elapsedSeconds = (millis() - startTime) / 1000;
                
                if (elapsedSeconds != lastElapsedSecond) {
                    mySerial.print("Listening (");
                    mySerial.print(recordingDurationS - elapsedSeconds);
                    mySerial.println("s)...");
                    lastElapsedSecond = elapsedSeconds;
                }

                esp_err_t result = i2s_read(INMP441_PORT, &listeningBuffer, bufferLen, &bytesIn, portMAX_DELAY);
                if (result == ESP_OK && isWebSocketConnected) {
                    client.sendBinary((const char*)listeningBuffer, bytesIn);
                }

                yield();
            }

            if (!stopRecordingUponSameTranscript) {
                const char* endOfRecordingSignal = END_OF_AUDIO_SIGNAL;
                client.send(endOfRecordingSignal);
                soundDetected = false;
                allowRecording = false;  // block during Thinking if we reached MAX_RECORDING_DURATION_MS
            }
            mySerial.println("Thinking...");
            stopRecordingUponSameTranscript = false;
        }

        if (client.available()) {
            client.poll();
        }
    }
}

// ########################################################################
// xTaskCreatePinnedToCore #2: handle audio playback (for robot speaking) #
// ########################################################################
void audioPlaybackTask(void* parameter) {
    while (1) {
        playAudio();
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

// ##########################################################
// Setup: Initialize WiFi, I2S, WebSocket, and async server #
// ##########################################################
void setup() {
    // initialize serial communication (over UART2) for Uno at 9600 baud rate
    mySerial.begin(9600, SERIAL_8N1, 12, 13); // 12 (RX), 13 (TX)
    // initialize serial communication for logging at 115200 baud rate
    Serial.begin(115200);

    // connect to Wi-Fi
    const char* connectedSSID = nullptr;
    while (!connectedSSID) {
        connectedSSID = connectToWiFi(ssid2, password2, staticIP2, gateway2, subnet2);
        if (!connectedSSID) {
            connectedSSID = connectToWiFi(ssid1, password1, staticIP1, gateway1, subnet1);
        }
    }

    // set websocket_server_host based on the connected network
    if (strcmp(connectedSSID, ssid2) == 0) {
        strcpy(websocket_server_host, websocket_server_host2);
    } else {
        strcpy(websocket_server_host, websocket_server_host1);
    }

    // set up KY-037 sound detector
    pinMode(KY037_PIN, INPUT_PULLUP);

    // set up INMP441 microphone
    inmp441_i2s_install();
    inmp441_i2s_setpin();
    i2s_start(INMP441_PORT);

    // set up MAX98357A amplifier
    pinMode(MAX98357A_SD, OUTPUT);
    digitalWrite(MAX98357A_SD, LOW);
    max98357a_i2s_install();
    max98357a_i2s_setpin();
    i2s_start(MAX98357A_PORT);

    // create mutex for audio playback buffer
    speakingBufferSemaphore = xSemaphoreCreateMutex();

    // attach interrupt handler for KY-037 sound detector
    attachInterrupt(digitalPinToInterrupt(KY037_PIN), handleSoundDetection, RISING);

    // create microphone task
    xTaskCreatePinnedToCore(microphoneTask, "microphoneTask", 10000, NULL, 1, NULL, 1); // core 1

    // create audio playback task
    xTaskCreatePinnedToCore(audioPlaybackTask, "audioPlayback", 4096, NULL, 1, NULL, 0); // core 0

    // start web server to receive commands from the computer
    server.on("/stopRecordingUponSameTranscript", handleStopRecordingUponSameTranscript);
    server.on("/allowRecordingWhenRobotThinksAndStaysQuiet", handleAllowRecordingWhenRobotThinksAndStaysQuiet);
    server.on("/command", handleCommand);
    server.begin();
}

// ##########################################################
// Loop: Do nothing after setup (tasks runs asynchronously) #
// ##########################################################
void loop() {
}