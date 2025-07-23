import serial
import time
from .gnss import GNSS
from .http import HTTP

class SIMA7672S:
    def __init__(self, port="/dev/ttyS0", baudrate=115200):
        """
        Initialize the SIMA7672S class and serial connection.

        :param port: Serial port for communication
        :param baudrate: Baudrate for serial communication
        """
        self.port = port
        self.baudrate = baudrate
        self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
        self.GNSS = GNSS(self)
        self.HTTP = HTTP(self)

    def SendAT(self, command: str, timeout: int | float, response: str = None, debug=False):
        """
        Send an AT command and read the response.

        :param command: AT command to send
        :param timeout: Timeout for waiting for response
        :param response: Expected response string
        :param debug: Enable debug output
        :return: Response from the modem
        """
        self.ser.write(f"{command}\r".encode())
        time.sleep(0.2)
        return self.ReadSerial(timeout, response, debug)

    def ReadSerial(self, timeout: int | float, response: str = None, debug=False):
        """
        Read data from the serial port.

        :param timeout: Timeout for reading
        :param response: Expected response string
        :param debug: Enable debug output
        :return: Data read from the serial port
        """
        temp = ""
        start = time.time()
        while time.time() - start < timeout:
            if self.ser.in_waiting > 0:
                c = self.ser.read(self.ser.in_waiting).decode()
                if debug:
                    print(c, end="")
                temp += c
            if response and response in temp:
                temp += "\n"
                break
        return temp
    
    def WakeUp(self, debug=False):
        self.SendAT("AT", 10, "OK", debug)
        self.SendAT("AT+CSCLK=0", 5, "OK", debug)