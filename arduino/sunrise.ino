#include <Adafruit_NeoPixel.h>
#include <Wire.h>

// Neopixel stuff
#define N_Pixels 106 //number of pixels in strand is:
// oxi: 34
// phylomeno: 106

#define LED_PIN 6 //NeoPixel strand is connected to this pin
Adafruit_NeoPixel strip = Adafruit_NeoPixel(N_Pixels, LED_PIN, NEO_GRB + NEO_KHZ800);

// i2C stuff
#define SLAVE_ADDRESS 0x04
uint8_t i2cCommand = 0;

// main loop wait configuration
int wait = 20;

// general fade loop vars
unsigned long currentFadeStart = 0;
unsigned long currentFadeEnd = 0;
uint8_t currentColor[] = {0, 0, 0};
uint8_t fadeCount = 0;

// sunrise loop vars
unsigned long sunriseStartTime = 0;
uint8_t startColor[] = {0, 0, 0};
int sunriseLoopStep = 0;
bool doSunrise = false;

// fixed color vars
bool doFixedColor = false;

// fire
bool doFire = false;
unsigned long nextFireLoop = 0;

void setup()
{
  // initialize serial port
  Serial.begin(9600);

  // initialize neopixel strip
  strip.begin();
  strip.setBrightness(255);//change how bright here
  strip.show();

  // initialize i2c as slave
  Wire.begin(SLAVE_ADDRESS);

  // define callbacks for i2c communication
  Wire.onReceive(receiveData);
  Wire.onRequest(sendData);

  // initial delay to let millis not be 0
  delay(1);

  // clear the strip
  colorWipe (strip.Color(0, 0, 0), 0);
}

// main loop
void loop() {
  sunrise();
  fire();
  //Serial.println((String)"Main loop wait at millis: " + millis());

  delay(wait);
}

// sunrise
bool sunrise() {
  if (! doSunrise) {
    // no sunrise happening!
    sunriseStartTime = 0;
    return false;
  }
  if (sunriseStartTime < 1) {
    Serial.println((String)"Sunrise starting");
    sunriseStartTime = millis();
    sunriseLoopStep = 0;
    currentFadeStart = 0;
    fadeCount = 0;
    colorWipe (strip.Color(0, 0, 0), 0);
    currentColor[0] = 0;
    currentColor[1] = 0;
    currentColor[2] = 0;
  }

  int sunriseData[][4] = {
    { 50,   0,   0,   5},
    { 50,   0,  20,  52},
    { 50,  25,  20,  60},
    { 50, 207,  87,  39},
    { 50, 220, 162,  16},
    { 50, 255, 165,   0},
    { 50, 255, 255,  30}
  };

  if (fade(currentColor, startColor, sunriseData[sunriseLoopStep][0], sunriseData[sunriseLoopStep][1], sunriseData[sunriseLoopStep][2], sunriseData[sunriseLoopStep][3])) {
    sunriseLoopStep++;
  }

  int fadeSteps = sizeof(sunriseData) / sizeof(int) / 4;
  if (sunriseLoopStep >= fadeSteps) {
    // reset all variables
    unsigned long duration = (millis() - sunriseStartTime) / 1000;
    Serial.println((String)"Sunrise ended after " + duration + " seconds.");
    sunriseLoopStep = 0;
    doSunrise = false;
  }
}

// fire
bool fire() {
  if (! doFire) {
    // no fire happening!
    nextFireLoop = 0;
    return false;
  }

  if (millis() < nextFireLoop) {
    return false;
  }

  uint16_t r = 255;
  uint16_t g = r-40;
  uint16_t b = 40;
  
  for (uint16_t i = 0; i < strip.numPixels(); i++) {
    uint16_t flicker = random(0,150);
    uint16_t r1 = r-flicker;
    uint16_t g1 = g-flicker;
    uint16_t b1 = b-flicker;
    if(r1<0) r1=0;
    if(g1<0) g1=0;
    if(b1<0) b1=0;
    strip.setPixelColor(i, strip.Color(r1, g1, b1));
    strip.show();
  }

  nextFireLoop = millis() + random(50,150);
}

// helper functions
// neopixel color fade loop
bool fade(uint8_t currentColor[], uint8_t startColor[], uint32_t fadeDuration, uint16_t redEnd, uint16_t greenEnd, uint16_t blueEnd) {
  if (currentFadeStart < 1) {
    // new fade loop. calculating and setting required things
    fadeCount++;
    currentFadeStart = millis();
    currentFadeEnd = currentFadeStart + (fadeDuration * 1000);
    startColor[0] = currentColor[0];
    startColor[1] = currentColor[1];
    startColor[2] = currentColor[2];
    Serial.print((String)"Fade " + fadeCount + " will take " + (currentFadeEnd - currentFadeStart) + " millis ");
    Serial.println((String)"from " + startColor[0] + ", " + startColor[1] + ", " + startColor[2] +" to " + redEnd + ", " + greenEnd + ", " + blueEnd);
  }

  unsigned long now = millis();
  currentColor[0] = map(now, currentFadeStart, currentFadeEnd, startColor[0], redEnd);
  currentColor[1] = map(now, currentFadeStart, currentFadeEnd, startColor[1], greenEnd);
  currentColor[2] = map(now, currentFadeStart, currentFadeEnd, startColor[2], blueEnd);

  colorWipe (strip.Color(currentColor[0], currentColor[1], currentColor[2]), 0);
  strip.show();

  if (millis() >= currentFadeEnd) {
    // current fade finished
    unsigned long endTime = millis();
    unsigned long fadeDuration = (endTime - currentFadeStart) / 1000;
    Serial.println((String)"Fade " + fadeCount + " ended after " + fadeDuration + " seconds.");
    currentFadeStart = 0;
    return true;
  } else {
    // current fade not yet finished
    return false;
  }
}

// fill the neopixel dots one after the other with a color
void colorWipe(uint32_t c, uint8_t wait) {
  for (uint16_t i = 0; i < strip.numPixels(); i++) {
    strip.setPixelColor(i, c);
  }
  strip.show();
}

// callback for received i2c data
void receiveData(int byteCount) {
  int numOfBytes = Wire.available();
  i2cCommand = (uint8_t) Wire.read();  //cmd

  Serial.print("I2c data received: ");
  Serial.println((String)"Command: " + i2cCommand);

  uint8_t i2cData[numOfBytes-1];
  for(int i=0; i<numOfBytes-1; i++){
    i2cData[i] = (uint8_t) Wire.read();
  }

  // number 1 = sunrise
  if (i2cCommand == 1) {
      Serial.println("Enabling sunrise");
      doSunrise = true;
      doFixedColor = false;
      doFire = false;
  } else if (i2cCommand == 2) {
      Serial.println("Enabling fixed color");
      doSunrise = false;
      doFixedColor = true;
      doFire = false;
      colorWipe (strip.Color(i2cData[0], i2cData[1], i2cData[2]), i2cData[3]);
  } else if (i2cCommand == 3) {
      // not yet implemented
      Serial.println("Enabling fade to color");
      doSunrise = false;
      doFixedColor = false;
      doFire = false;
  } else if (i2cCommand == 4) {
      // not yet implemented
      Serial.println("Enabling rainbow");
      doSunrise = false;
      doFixedColor = false;
      doFire = false;
  } else if (i2cCommand == 5) {
      // not yet implemented
      Serial.println("Enabling rainbow");
      doSunrise = false;
      doFixedColor = false;
      doFire = true;
  } else if (i2cCommand == 0) {
      Serial.println("Disabling everything");
      doSunrise = false;
      doFixedColor = false;
      doFire = false;
      colorWipe (strip.Color(0, 0, 0), 0);
  } else {
    Serial.println("Unknown i2c command");
  }
}

// callback for i2c sending data
void sendData() {
  Wire.write(i2cCommand);
}
