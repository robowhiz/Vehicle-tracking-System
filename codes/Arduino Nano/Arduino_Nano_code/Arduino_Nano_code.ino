#include <Arduino.h>
#include <SoftwareSerial.h>
#include <Adafruit_Fingerprint.h>

SoftwareSerial RPi(5, 6);

#define KEYIN 3
#define WAKEUP_PIN 2

#define FULVL A1
#define MAXFUELLEVEL 1023
#define MINFUELLEVEL 0
#define MINPERCENT 0
#define MAXPERCENT 100
#define SAMPLE_INTERVAL 500
#define REPORT_INTERVAL 15000
#define SAMPLES_PER_REPORT 30

uint16_t fuelBuffer = 0;

uint8_t getFuelLevel();

#define ALCOHOLSENSOR A0
#define ALCOHOLTHRESHOLD 400
#define BUZZER 7
#define IGNITION 8
#define IGNITIONON LOW
#define IGNITIONOFF HIGH

uint32_t buzzertimer;

uint8_t getalcoholState();

SoftwareSerial mySerial(9, 10);
Adafruit_Fingerprint finger = Adafruit_Fingerprint(&mySerial);

#define TCH_PIN 11

uint8_t validFingerprintID;
uint32_t fingerprintSensorAddress;

uint8_t verifyFingerprint();
uint16_t getFingerprintID();

struct fromRPi
{
    uint8_t initializedSystem;
    uint8_t validFingerprintID;
    uint8_t ignitionState;
} r_data;

struct toRPi
{
    uint16_t alcoholValue;
    uint8_t alcoholDetected;
    uint8_t ignitionState;
    uint8_t validFingerprintFound;
    uint8_t fingerprintVerified;
    uint8_t fuelLevel;
    uint8_t keyState;
    uint8_t error;
} t_data;

#define NO_ERROR 0x00
#define FINGERPRINT_SENSOR_FALIED 0x01
#define FINGERPRINT_VERIFY 0x02

#define STATUSLED 12
uint8_t LEDState;

void statusLEDControl();

uint8_t systemInitialized = false;
uint32_t looptimer;
uint32_t loopcounter = 0;

uint8_t initializeSystem();
void resetVariables();

// #define DEBUG
// #define DEBUG_SERIAL

#ifdef DEBUG_SERIAL
struct debug
{
    uint16_t alcoholValue;
    uint8_t alcoholDetected;
    uint8_t ignitionState;
    uint8_t validFingerprintFound;
    uint8_t fingerprintVerified;
    uint8_t fuelLevel;
    uint8_t keyState;
    uint8_t error;
    uint8_t initializedSystem;
    uint8_t validFingerprintID;
    uint8_t systemInitialized = false;
    uint32_t looptimer;
    uint32_t loopcounter;
    uint8_t LEDState;
    uint32_t buzzertimer;
    uint16_t fuelBuffer;
} data;
#endif

void setup()
{
#if defined(DEBUG) || defined(DEBUG_SERIAL)
    Serial.begin(115200);
#endif
    RPi.begin(57600);

    pinMode(WAKEUP_PIN, OUTPUT);
    pinMode(KEYIN, INPUT);
    pinMode(IGNITION, OUTPUT);
    pinMode(FULVL, INPUT);
    pinMode(ALCOHOLSENSOR, INPUT);
    pinMode(BUZZER, OUTPUT);
    pinMode(TCH_PIN, INPUT_PULLUP);
    pinMode(STATUSLED, OUTPUT);

    attachInterrupt(digitalPinToInterrupt(KEYIN), resetVariables, CHANGE);

    finger.begin(57600);
    if (!finger.verifyPassword())
        t_data.error = FINGERPRINT_SENSOR_FALIED;
    else
        t_data.error = NO_ERROR;
    finger.getParameters();
    fingerprintSensorAddress = finger.device_addr;

#ifdef DEBUG
    Serial.print("error ");
    Serial.println(t_data.error);
    Serial.print("fingerprintSensorAddress ");
    Serial.println(fingerprintSensorAddress);
#endif
    RPi.listen();

#ifdef DEBUG_SERIAL
    Serial.write((byte *)&data, sizeof(debug));
#endif
    looptimer = micros();
}

void loop()
{
    t_data.keyState = digitalRead(KEYIN);
    if (t_data.keyState == HIGH)
    {
        if (!systemInitialized)
            initializeSystem();

        else
        {
            if (!t_data.fingerprintVerified)
                t_data.fingerprintVerified = verifyFingerprint();

            RPi.listen();
            if (RPi.available() >= sizeof(fromRPi))
            {
#ifdef DEBUG
                Serial.println("\nReceived from rpi ");
#endif
                RPi.readBytes((byte *)&r_data, sizeof(fromRPi));
                if (t_data.ignitionState != r_data.ignitionState)
                {
#ifdef DEBUG
                    Serial.println("changed");
#endif
                    uint8_t data = r_data.ignitionState;
                    t_data.ignitionState = data;
                    digitalWrite(IGNITION, t_data.ignitionState);
                }
                RPi.write((byte *)&t_data, sizeof(toRPi));
#ifdef DEBUG
                Serial.println("\nSent to rpi ");
#endif
            }
        }
        getFuelLevel();
        getalcoholState();
        statusLEDControl();
    }

#ifdef DEBUG_SERIAL
    Serial.write((byte *)&data, sizeof(debug));
#endif

    while (micros() - looptimer < 20000)
        ;
    looptimer = micros();
    loopcounter++;
}

uint8_t initializeSystem()
{
    if (RPi.available() >= sizeof(fromRPi))
    {
#ifdef DEBUG
        Serial.println("Received from rpi ");
#endif

        RPi.readBytes((byte *)&r_data, sizeof(fromRPi));
        systemInitialized = r_data.initializedSystem;
        validFingerprintID = r_data.validFingerprintID;

        mySerial.listen();
        if (!finger.verifyPassword())
            t_data.error = FINGERPRINT_SENSOR_FALIED;
        else
            t_data.error = NO_ERROR;
        finger.getParameters();
        fingerprintSensorAddress = finger.device_addr;

#ifdef DEBUG
        Serial.print("fingerprintSensorAddress ");
        Serial.println(fingerprintSensorAddress, HEX);
#endif
        RPi.listen();
        RPi.write((byte *)&fingerprintSensorAddress, sizeof(fingerprintSensorAddress));
    }
}

void resetVariables()
{
    t_data.keyState = digitalRead(KEYIN);
    if (t_data.keyState == HIGH)
    {
        digitalWrite(WAKEUP_PIN, HIGH);
        digitalWrite(IGNITION, IGNITIONOFF);
        loopcounter = 1;
        fuelBuffer = 0;
        buzzertimer = 0;
        systemInitialized = false;
        validFingerprintID = 0;
        t_data.error = NO_ERROR;
        t_data.ignitionState = IGNITIONOFF;
        t_data.alcoholDetected = false;
        t_data.fingerprintVerified = false;
        t_data.validFingerprintFound = false;
    }
    else
    {
        digitalWrite(WAKEUP_PIN, LOW);
        digitalWrite(IGNITION, IGNITIONON);
        t_data.ignitionState = IGNITIONON;
    }
}

uint8_t getFuelLevel()
{
    if (loopcounter % SAMPLE_INTERVAL == 0)
    {
        fuelBuffer += analogRead(FULVL);

        if (loopcounter % REPORT_INTERVAL == 0)
        {
            t_data.fuelLevel = map(fuelBuffer / SAMPLES_PER_REPORT, MINFUELLEVEL, MAXFUELLEVEL, MINPERCENT, MAXPERCENT);
            fuelBuffer = 0;
            loopcounter = 0;
        }
    }
}

uint8_t getalcoholState()
{
    t_data.alcoholValue = analogRead(ALCOHOLSENSOR);

    if (t_data.alcoholValue > ALCOHOLTHRESHOLD)
    {
        buzzertimer = millis();
        t_data.alcoholDetected = true;
        t_data.ignitionState = IGNITIONOFF;
        digitalWrite(BUZZER, HIGH);
        digitalWrite(IGNITION, IGNITIONOFF);
    }
    else if (buzzertimer && millis() - buzzertimer > 3000)
    {
        buzzertimer = 0;
        digitalWrite(BUZZER, LOW);
        t_data.alcoholDetected = false;
    }
}

uint8_t verifyFingerprint()
{
    t_data.error = FINGERPRINT_VERIFY;
    if (!digitalRead(TCH_PIN))
    {
#ifdef DEBUG
        Serial.println("Finger detected, trying to capture...");
#endif
        RPi.listen();
        if (RPi.available() >= sizeof(fromRPi))
        {
            RPi.readBytes((byte *)&r_data, sizeof(fromRPi));
            RPi.write((byte *)&t_data, sizeof(toRPi));
#ifdef DEBUG
            Serial.println("Received from rpi ");
#endif
        }
        delay(10);
        mySerial.listen();
        uint16_t result = getFingerprintID();
        if (result == validFingerprintID)
        {
#ifdef DEBUG
            Serial.println("Found valid fingerprint");
#endif
            t_data.validFingerprintFound = true;
            t_data.error = NO_ERROR;
            return true;
        }
        else if (result != -1)
        {
#ifdef DEBUG
            Serial.println("Found invalid fingerprint");
#endif
            t_data.error = NO_ERROR;
            t_data.validFingerprintFound = false;
        }
        else
        {
            t_data.error = FINGERPRINT_SENSOR_FALIED;
        }
    }
    else
    {
    }
    RPi.listen();
    return false;
}

uint16_t getFingerprintID()
{
    int result = finger.getImage();
    if (result != FINGERPRINT_OK)
    {
        return -1;
    }

    result = finger.image2Tz();
    if (result != FINGERPRINT_OK)
    {
        return -1;
    }

    result = finger.fingerSearch();
    if (result != FINGERPRINT_OK)
    {
        return -1;
    }

    return finger.fingerID;
}

void statusLEDControl()
{
    if (t_data.error == NO_ERROR)
        digitalWrite(STATUSLED, LOW);

    else if (t_data.error == FINGERPRINT_SENSOR_FALIED)
    {
        if (loopcounter % 25 == 0)
        {
            digitalWrite(STATUSLED, LEDState);
            LEDState = !LEDState;
        }
    }
    else if (t_data.error == FINGERPRINT_VERIFY)
    {
        digitalWrite(STATUSLED, HIGH);
        LEDState = HIGH;
    }
}