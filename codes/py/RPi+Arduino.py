# import RPi.GPIO as GPIO
from SIMA7672S import SIMA7672S
import os
import serial
import struct
import json
import time
import subprocess
import sys
import io

# GPIO.setmode(GPIO.BCM)
# GPIO.setup(3, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# def shutdown():
#     print("Shutdown initiated")
#     ArduSer.close()
#     os.system("sudo shutdown -h now")

# GPIO.add_event_detect(3, GPIO.FALLING, callback=shutdown, bouncetime=2000)

initializedSystem = 0
validFingerprintID = 0
ignitionState = 1 #1 is OFF and 0 is ON
todata = struct.pack("BBB", initializedSystem, validFingerprintID, ignitionState)

alcoholValue = 0
alcoholDetected = 0
validFingerprintFound = 0
fingerprintVerified = 0
fuelLevel = 0
keyState = 0
error = 0

ArduSer = serial.Serial("/dev/ttyAMA3", 57600)

PROJECT_ID = "your-firebase-project-id"
DATABASE_NAME = "(default)"
COLLECTION_NAME = "vehicles"
VEHICLE_ID = "your-vehicle-id"
FIRESTORE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/{DATABASE_NAME}/documents:commit"
FIREBASE_URL = f"https://smart-vehicle-tracking-s-dbf99-default-rtdb.firebaseio.com/VehicleLocation/{VEHICLE_ID}.json"
FINGERPRINT_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/{DATABASE_NAME}/documents/{COLLECTION_NAME}/{VEHICLE_ID}/"
NUMBER_OF_DAYS = 100

sim = SIMA7672S()
sleep_time = 300
firestoreDATA = []
firebaseDATA = {}

class DualOutput(io.TextIOBase):
    def __init__(self):
        super().__init__()
        date_stamp = time.strftime("%d-%m-%Y", time.localtime(time.time()))
        self.file = open(f"output/{date_stamp}.txt", "a+")
        self.txt:str = ""

    def write(self, text):
        time_stamp = time.ctime(time.time())
        sys.__stdout__.write(text)  # Output to the console
        self.txt += text
        while "\n" in self.txt:
            index = self.txt.index("\n")
            self.file.write(time_stamp + " -> " + self.txt[:index + 1])   # Write to the file if newline is found
            self.file.flush()       # Ensure data is written to the file
            self.txt = self.txt[index + 1:]

    def close(self):
        time_stamp = time.ctime(time.time())
        self.file.write(time_stamp + " -> " + self.txt + "\n\n")   # Write to the file if newline is found
        self.file.close()           # Close the file when done

# Redirect sys.stdout to both console and file
sys.stdout = DualOutput()

def setSystemTime(dt):
    try:
        subprocess.run(["sudo", "timedatectl", "set-timezone", "Asia/Kolkata"], check=True)
        subprocess.run(["sudo", "date", "-u", dt], check=True)
        print(f"System time updated to: {dt}")
    except subprocess.CalledProcessError as e:
        print(f"Error setting system time: {e}")

def updateTime():
    while True:
        GNSSData = sim.GNSS.getGNSSData(debug=True)
        if GNSSData:
            datestr = GNSSData["Date"]
            timestr = GNSSData["UTC-time"]
            formatedDateTime = f"{datestr[2:4]}{datestr[0:2]}{timestr[0:4]}20{datestr[4:6]}.{timestr[4:6]}"

            setSystemTime(formatedDateTime)
            break
        time.sleep(1)

def updateDATA(debug=False):
    global alcoholValue, alcoholDetected, ignitionState, validFingerprintFound, fingerprintVerified, fuelLevel, keyState, error
    todata = struct.pack("BBB", initializedSystem, validFingerprintID, ignitionState)
    ArduSer.write(todata)

    GNSSData = sim.GNSS.getGNSSData(debug=debug)
    LatLog = sim.GNSS.getFormattedLatLon(GNSSData)
    time_stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.localtime(time.time()))

    while ArduSer.in_waiting < 9:
        pass
    
    Adata = struct.unpack("hBBBBBBB", ArduSer.read(9))
    alcoholValue = int(Adata[0])
    alcoholDetected = int(Adata[1])
    ignitionState = int(Adata[2])
    validFingerprintFound = int(Adata[3])
    fingerprintVerified = int(Adata[4])
    fuelLevel = int(Adata[5])
    keyState = int(Adata[6])
    error = int(Adata[7])

    data = {
        "mapValue": {
            "fields": {
                "alcoholValue": {"integerValue": alcoholValue},
                "alcoholDetected": {"integerValue": alcoholDetected},
                "latitude": {"doubleValue": LatLog[0]},
                "longitude": {"doubleValue": LatLog[1]},
                "speed": {"doubleValue": GNSSData["speed"]},
                "fuelLevel": {"integerValue": fuelLevel},
                "keyState": {"integerValue": keyState},
                "error": {"integerValue": error},
                "timestamp": {"timestampValue": time_stamp},
            }
        }
    }
    print(data, end="\n\n")
    firestoreDATA.append(data)
    
    date_stamp = time.strftime("%d-%m-%Y", time.localtime(time.time()))
    data = data["mapValue"]["fields"]
    with open(f"log/{date_stamp}.txt", "a+") as file:
        file.write(json.dumps(data)+",\n")
        file.close()
    
    data = {
        "timestamp":time_stamp, 
        "latitude":LatLog[0], 
        "longitude":LatLog[1],
        "speed": 0.0,
        "fuelLevel":fuelLevel,
        "keyState": keyState
        }
    firebaseDATA.update(data)

def firestoreJSON(arrayData):
    date_stamp = time.strftime("%d-%m-%Y", time.localtime(time.time()))
    data = {
        "writes": [
            {
                "transform": {
                    "document": f"projects/{PROJECT_ID}/databases/{DATABASE_NAME}/documents/{COLLECTION_NAME}/{your-firebase-project-id}/tracking/{date_stamp}",
                    "fieldTransforms": [
                        {
                            "fieldPath": "data",
                            "appendMissingElements": {"values": arrayData},
                        }
                    ],
                }
            }
        ]
    }
    return json.dumps(data)

def validateFingerprintSensor():
    try:
        global validFingerprintID, initializedSystem, ignitionState
        httpResponse = sim.HTTP.SendHTTPRequest(FINGERPRINT_URL, debug = True)
        if httpResponse and httpResponse[1] == 200:
            reponse:str = sim.HTTP.ReadHTTPResponse(httpResponse[2])
            reponse = reponse[reponse.index("{"):reponse.rindex("}")+1]
            reponse = json.loads(reponse)
            validFingerprintID = int(reponse["fields"]["VehicleDetails"]["mapValue"]["fields"]["assignedTo"]["integerValue"])
             
            todata = struct.pack("BBB", initializedSystem, validFingerprintID, ignitionState)
            ArduSer.write(todata)
            print("validateFingerprintSensor")
            
            while ArduSer.in_waiting < 4:
                pass

            print("receiverd")
            fingerprintSensorAddress = int(reponse["fields"]["VehicleDetails"]["mapValue"]["fields"]["FingerprintSensorAddress"]["integerValue"])
            fingerprintSensorAddress = (fingerprintSensorAddress).to_bytes(4, byteorder='big')
            time.sleep(1)
            if fingerprintSensorAddress == ArduSer.read(4):
                print("verified")
                initializedSystem = 1
                ignitionState = 0
                todata = struct.pack("BBB", initializedSystem, validFingerprintID, ignitionState)
                ArduSer.write(todata)
                time.sleep(0.1)
                while ArduSer.in_waiting < 4:
                    pass
                ArduSer.read(4)
        else :
            initializedSystem = 0
            todata = struct.pack("BBB", initializedSystem, validFingerprintID, ignitionState)
            ArduSer.write(todata)
            while ArduSer.in_waiting < 4:
                pass
            ArduSer.read(4)
        time.sleep(1)
        sim.HTTP.terminateHTTP(debug=True)
    except Exception as e:
        print(e)
        import traceback
        traceback.print_exc()
    
    except KeyboardInterrupt as e:
        print(e)
        sim.SendAT("AT+HTTPTERM", 1, debug = True)
        sim.ser.close()
        ArduSer.close()
        time.sleep(1)

def verifyFingerprint():
    print("verifyFingerprint")
    global todata
    ArduSer.write(todata)
    while ArduSer.in_waiting < 9:
        pass
    global fingerprintVerified, ignitionState, validFingerprintFound
    data = struct.unpack("hBBBBBBB", ArduSer.read(9))
    print(data)
    validFingerprintFound = int(data[3])
    fingerprintVerified = int(data[4])
    if validFingerprintFound == 1:
        return True
    else:
        return False

sim.GNSS.Initialize(sim.GNSS.StartMode.HOT, debug=True)

validateFingerprintSensor()
time.sleep(5)
while not verifyFingerprint():
    time.sleep(5)

# updateTime()

while True:
    try:
        updateDATA(debug=True)

        httpResponse = sim.HTTP.SendHTTPRequest(FIREBASE_URL, sim.HTTP.HTTPRequest.PUT, json.dumps(firebaseDATA), debug=True)
        time.sleep(5)
        if httpResponse and httpResponse[1] == 200:
            print(sim.HTTP.ReadHTTPResponse(httpResponse[2]))
        elif httpResponse:
            print("Failed sending data to Firebase")
            print(sim.HTTP.ReadHTTPResponse(httpResponse[2]))
        time.sleep(1)
        sim.HTTP.terminateHTTP(debug=True)

        if int(time.strftime("%M", time.localtime(time.time()))) in range(55, 60):
            httpResponse = sim.HTTP.SendHTTPRequest(FIRESTORE_URL, sim.HTTP.HTTPRequest.POST, firestoreJSON(firestoreDATA), debug=True)
            time.sleep(5)
            if httpResponse and httpResponse[1] == 200:
                firestoreDATA = []
                print(sim.HTTP.ReadHTTPResponse(httpResponse[2]))
            elif httpResponse:
                print("Failed sending data to firestore")
                print(sim.HTTP.ReadHTTPResponse(httpResponse[2]))
            time.sleep(1)
            sim.HTTP.terminateHTTP(debug=True)

            if int(time.strftime("%H", time.localtime(time.time()))) == 0:
                DATE = time.strftime("%d-%m-%Y", time.localtime(time.time() - 86400*NUMBER_OF_DAYS))
                DELETE_URL = f"https://firestore.googleapis.com/v1beta1/projects/{PROJECT_ID}/databases/{DATABASE_NAME}/documents/{COLLECTION_NAME}/{your-firebase-project-id}/tracking/{DATE}"

                httpResponse = sim.HTTP.SendHTTPRequest(DELETE_URL, sim.HTTP.HTTPRequest.DELETE, debug=True)
                time.sleep(5)
                if httpResponse and httpResponse[1] == 200:
                    firestoreDATA = []
                    print(sim.HTTP.ReadHTTPResponse(httpResponse[2]))
                elif httpResponse:
                    print("Failed sending data to firestore")
                    print(sim.HTTP.ReadHTTPResponse(httpResponse[2]))
                time.sleep(1)
                sim.HTTP.terminateHTTP(debug=True)
        time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("Shutting down gracefully...")
        sim.HTTP.terminateHTTP(debug=True)
        sim.GNSS.Shutdown(debug=True)
        sim.ser.close()
        ArduSer.close()
        time.sleep(3)
        sys.stdout.close()
        sys.stdout = sys.__stdout__
        break

    except Exception as e:
        print(f"An error occurred: {e}", "executed")
        import traceback
        traceback.print_exc()
        sim.HTTP.terminateHTTP(debug=True)
        print("not executed")
        sim.GNSS.Shutdown(debug=True)
        sim.ser.close()
        ArduSer.close()
        time.sleep(3)
        sys.stdout.close()
        sys.stdout = sys.__stdout__
        break