// ################################################################
// Production sketch for ESP32-CAM to send images to the computer #
// ################################################################

// takes care of ESP32-CAM - computer WiFi connection
#include <WiFi.h>
// takes care of asynchronous TCP connections for the server
#include <AsyncTCP.h>
// takes care of the asynchronous HTTP server
#include <ESPAsyncWebServer.h>
// takes care of the ESP32-CAM camera
#include <esp_camera.h>

// ###############
// Configuration #
// ###############

// Primary network configuration (home WiFi)
const char* ssid1 = "";                                 // Home WiFi SSID
const char* password1 = "";                             // Home WiFi password
IPAddress staticIP1(192, 168, 1, 181);                  // Static IP for home network
IPAddress gateway1(192, 168, 1, 1);                     // Gateway for home network
IPAddress subnet1(255, 255, 255, 0);                    // Subnet mask for home network

// Secondary network configuration (phone hotspot)
const char* ssid2 = "";                                 // Phone hotspot SSID
const char* password2 = "";                             // Phone hotspot password
IPAddress staticIP2(172, 20, 10, 11);                   // Static IP for hotspot
IPAddress gateway2(172, 20, 10, 1);                     // Gateway for hotspot
IPAddress subnet2(255, 255, 255, 0);                    // Subnet mask for hotspot

// Web server initialization
AsyncWebServer server(80);                              // Server on port 80

// Content type for JPEG data
static const char * JPG_CONTENT_TYPE = "image/jpeg";    // MIME type for JPEG images
// MIME (Multipurpose Internet Mail Extensions) is a way to describe a file format

// Start of https://gist.github.com/me-no-dev/d34fba51a8f059ac559bf62002e61aa3
class AsyncBufferResponse: public AsyncAbstractResponse {
    private:
        uint8_t * _buf;
        size_t _len;
        size_t _index;
    public:
        AsyncBufferResponse(uint8_t * buf, size_t len, const char * contentType){
            _buf = buf;
            _len = len;
            _callback = nullptr;
            _code = 200;
            _contentLength = _len;
            _contentType = contentType;
            _index = 0;
        }
        
        ~AsyncBufferResponse(){
            if(_buf != nullptr){
                free(_buf);
            }
        }
        
        bool _sourceValid() const { return _buf != nullptr; }
        
        virtual size_t _fillBuffer(uint8_t *buf, size_t maxLen) override{
            size_t ret = _content(buf, maxLen, _index);
            if(ret != RESPONSE_TRY_AGAIN){
                _index += ret;
            }
            return ret;
        }
        
        size_t _content(uint8_t *buffer, size_t maxLen, size_t index){
            memcpy(buffer, _buf+index, maxLen);
            if((index+maxLen) == _len){
                free(_buf);
                _buf = nullptr;
            }
            return maxLen;
        }
};

class AsyncFrameResponse: public AsyncAbstractResponse {
    private:
        camera_fb_t * fb;
        size_t _index;
    public:
        AsyncFrameResponse(camera_fb_t * frame, const char * contentType){
            _callback = nullptr;
            _code = 200;
            _contentLength = frame->len;
            _contentType = contentType;
            _index = 0;
            fb = frame;
        }
        
        ~AsyncFrameResponse(){
            if(fb != nullptr){
                esp_camera_fb_return(fb);
            }
        }
        
        bool _sourceValid() const { return fb != nullptr; }
        
        virtual size_t _fillBuffer(uint8_t *buf, size_t maxLen) override{
            size_t ret = _content(buf, maxLen, _index);
            if(ret != RESPONSE_TRY_AGAIN){
                _index += ret;
            }
            return ret;
        }
        
        size_t _content(uint8_t *buffer, size_t maxLen, size_t index){
            memcpy(buffer, fb->buf+index, maxLen);
            if((index+maxLen) == fb->len){
                esp_camera_fb_return(fb);
                fb = nullptr;
            }
            return maxLen;
        }
};

void sendJpg(AsyncWebServerRequest *request){
    camera_fb_t * fb = esp_camera_fb_get();
    if (fb == NULL) {
        log_e("Camera frame failed");
        request->send(501);
        return;
    }

    if(fb->format == PIXFORMAT_JPEG){
        AsyncFrameResponse * response = new AsyncFrameResponse(fb, JPG_CONTENT_TYPE);
        if (response == NULL) {
            log_e("Response alloc failed");
            request->send(501);
            return;
        }
        response->addHeader("Access-Control-Allow-Origin", "*");
        request->send(response);
        return;
    }

    size_t jpg_buf_len = 0;
    uint8_t * jpg_buf = NULL;
    unsigned long st = millis();
    bool jpeg_converted = frame2jpg(fb, 80, &jpg_buf, &jpg_buf_len);
    esp_camera_fb_return(fb);
    
    if(!jpeg_converted){
        log_e("JPEG compression failed: %lu", millis());
        request->send(501);
        return;
    }
    log_i("JPEG: %lums, %uB", millis() - st, jpg_buf_len);

    AsyncBufferResponse * response = new AsyncBufferResponse(jpg_buf, jpg_buf_len, JPG_CONTENT_TYPE);
    if (response == NULL) {
        log_e("Response alloc failed");
        request->send(501);
        return;
    }
    response->addHeader("Access-Control-Allow-Origin", "*");
    request->send(response);
}
// End of https://gist.github.com/me-no-dev/d34fba51a8f059ac559bf62002e61aa3

// ###########################################################################
// Helper 1: update camera settings upon HTTP POST request from the computer #
// ###########################################################################
void handleCameraConfig(AsyncWebServerRequest *request) {
    camera_config_t config;

    if (request->method() == HTTP_POST) {
        // process JPEG quality parameter
        if (request->hasParam("jpeg_quality", true)) {
            String jpegQuality = request->getParam("jpeg_quality", true)->value();
            int jpegQualityInt = jpegQuality.toInt();
            if (jpegQualityInt < 0 || jpegQualityInt > 63) {
                request->send(400, "text/plain", "Parameter 'jpeg_quality' is invalid");
                return;
            }
            else {
                config.jpeg_quality = jpegQualityInt;
            }
        } else {
            request->send(400, "text/plain", "Parameter 'jpeg_quality' is missing");
            return;
        }

        // process frame size parameter
        if (request->hasParam("frame_size", true)) {
            String frameSize = request->getParam("frame_size", true)->value();
            if (strcmp(frameSize.c_str(), "FRAMESIZE_QVGA") == 0) {
                config.frame_size = FRAMESIZE_QVGA;                                 // 320x240
            }
            else if (strcmp(frameSize.c_str(), "FRAMESIZE_VGA") == 0) {
                config.frame_size = FRAMESIZE_VGA;                                  // 640x480
            }
            else if (strcmp(frameSize.c_str(), "FRAMESIZE_SVGA") == 0) {
                config.frame_size = FRAMESIZE_SVGA;                                 // 800x600
            }
            else if (strcmp(frameSize.c_str(), "FRAMESIZE_XGA") == 0) {
                config.frame_size = FRAMESIZE_XGA;                                  // 1024x768
            }
            else if (strcmp(frameSize.c_str(), "FRAMESIZE_SXGA") == 0) {
                config.frame_size = FRAMESIZE_SXGA;                                 // 1280x1024
            }
            else if (strcmp(frameSize.c_str(), "FRAMESIZE_UXGA") == 0) {
                config.frame_size = FRAMESIZE_UXGA;                                 // 1600x1200
            }
            else {
                request->send(400, "text/plain", "Parameter 'frame_size' is invalid");
                return;
            }
        } else {
            request->send(400, "text/plain", "Parameter 'frame_size' is missing");
            return;
        }

        // set fixed camera configuration parameters
        config.ledc_channel = LEDC_CHANNEL_0;       // xclk channel
        config.ledc_timer = LEDC_TIMER_0;           // timer for PWM
        config.pixel_format = PIXFORMAT_JPEG;       // output as JPEG
        config.fb_count = 1;                        // 1 frame buffer
        config.xclk_freq_hz = 20000000;             // 20 MHz xclk (clock) frequency
        config.grab_mode = CAMERA_GRAB_LATEST;      // latest frame
        config.fb_location = CAMERA_FB_IN_PSRAM;    // store in PSRAM

        // ensure the pin mapping matches Ai-Thinker's
        
        // 8 parallel data lines for the camera to send each pixel's bits one at a time;
        // together, these pins form an 8-bit output bus.
        config.pin_d0 = 32;
        config.pin_d1 = 35;
        config.pin_d2 = 34;
        config.pin_d3 = 5;
        config.pin_d4 = 39;
        config.pin_d5 = 18;
        config.pin_d6 = 36;
        config.pin_d7 = 19;

        config.pin_xclk = 27;           // xclk (external clock) input
        config.pin_pclk = 21;           // pixel clock
        config.pin_vsync = 25;
        config.pin_href = 26;
        config.pin_sscb_sda = 22;       // serial data line
        config.pin_sscb_scl = 23;       // serial clock line
        config.pin_pwdn = -1;           // power-down
        config.pin_reset = 15;          // reset

        // apply configuration
        esp_camera_deinit();
        esp_err_t err = esp_camera_init(&config);
        if (err != ESP_OK) {
            request->send(500, "text/plain", "Camera config update failed");
        }
        else {
            request->send(200, "text/plain", "Camera config updated");
        }
    } else {
        request->send(405, "text/plain", "Method Not Allowed");
    }
}

// ##########################################################
// Helper 2: attempt to connect to (specified) WiFi network #
// ##########################################################
bool connectToWiFi(const char* ssid, const char* password, IPAddress staticIP, IPAddress gateway, IPAddress subnet) {
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
            return true;
        }
        delay(1000);
        Serial.print(".");
    }
    Serial.println("Connection failed.");
    return false;
}

// ################################################
// Setup: Initialize camera, WiFi, and web server #
// ################################################
void setup() {
    // start serial at 115200 bits per second
    Serial.begin(115200);

    // configure camera
    camera_config_t config;
    config.ledc_channel = LEDC_CHANNEL_0;       // xclk channel
    config.ledc_timer = LEDC_TIMER_0;           // timer for PWM
    config.pixel_format = PIXFORMAT_JPEG;       // output as JPEG
    config.frame_size = FRAMESIZE_VGA;          // 640x480 resolution
    config.jpeg_quality = 12;                   // quality 12 (0-63, lower is better)
    config.fb_count = 1;                        // 1 frame buffer
    config.xclk_freq_hz = 20000000;             // 20 MHz xclk (clock) frequency
    config.grab_mode = CAMERA_GRAB_LATEST;      // latest frame
    config.fb_location = CAMERA_FB_IN_PSRAM;    // store in PSRAM

    // ensure the pin mapping matches M5Stack Wide's

    // 8 parallel data lines for the camera to send each pixel's bits one at a time;
    // together, these pins form an 8-bit output bus.
    config.pin_d0 = 32;
    config.pin_d1 = 35;
    config.pin_d2 = 34;
    config.pin_d3 = 5;
    config.pin_d4 = 39;
    config.pin_d5 = 18;
    config.pin_d6 = 36;
    config.pin_d7 = 19;

    config.pin_xclk = 27;       // xclk (external clock) input
    config.pin_pclk = 21;       // pixel clock
    config.pin_vsync = 25;
    config.pin_href = 26;
    config.pin_sscb_sda = 22;   // serial data line
    config.pin_sscb_scl = 23;   // serial clock line
    config.pin_pwdn = -1;       // power-down
    config.pin_reset = 15;      // reset

    // initialize camera
    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
        Serial.printf("Camera init failed with error 0x%x", err);
        return;
    }

    // attempt WiFi connection to secondary network, then attempt connection to primary network
    // Note they are switched (i.e., primary as fallback network) as the hotspot lets 
    // us connect from anywhwere (e.g., outside home), and while it was originally meant as
    // secondary network, it became the 'primary' option
    bool connected = false;
    while (!connected) {
        connected = connectToWiFi(ssid2, password2, staticIP2, gateway2, subnet2);
        if (!connected) {
            connected = connectToWiFi(ssid1, password1, staticIP1, gateway1, subnet1);
        }
    }

    // configure web server routes
    server.on("/image.jpg", HTTP_GET, sendJpg);
    server.on("/camera_config", HTTP_POST, handleCameraConfig);

    // start server
    server.begin();
}

// ###########################################################
// Loop: Do nothing after setup (server runs asynchronously) #
// ###########################################################
void loop() {
}