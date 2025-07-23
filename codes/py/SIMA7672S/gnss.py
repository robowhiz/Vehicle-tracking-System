import time

class GNSS:
    def __init__(self, outer):
        """
        Initialize GNSS object.

        :param outer: Reference to outer class (likely modem controller)
        """
        self.outer = outer

    class StartMode:
        COLD = "AT+CGPSCOLD"
        WARM = "AT+CGPSWARM"
        HOT = "AT+CGPSHOT"

    def Initialize(self, mode = StartMode.COLD, debug: bool = False):
        """
        Initialize GNSS module.

        :param debug: Enable debug output
        """
        self.outer.SendAT("AT+CGNSSPWR=1", 10, "READY!", debug)
        time.sleep(0.2)
        self.outer.SendAT(mode, 10, "OK", debug)
        time.sleep(0.2)
        self.outer.SendAT("AT+CGNSSPORTSWITCH=1,1", 1, debug=debug)
        time.sleep(0.2)

    def Shutdown(self, debug: bool = False):
        """
        Shutdown GNSS module.

        :param debug: Enable debug output
        """
        self.outer.SendAT("AT+CGNSSPWR=0", 2, debug=debug)
        time.sleep(3)

    def getGNSSData(self, debug: bool = False):
        """
        Retrieve GNSS data.

        :param debug: Enable debug output
        :return: Dictionary containing GNSS data or None if data is incomplete
        """
        gnss_info = self.outer.SendAT("AT+CGNSSINFO", 3, "OK", debug=debug)
        info_list = gnss_info.split(",")

        if len(info_list) > 16:
            gnss = {
                "Mode": info_list[0],
                "GPS-SVs": info_list[1],
                "GLONASS-SVs": info_list[2],
                "BEIDOU-SVs": info_list[3],
                "GALILEO-SVs": info_list[4],
                "Latitude": info_list[5],
                "N/S": info_list[6],
                "Longitude": info_list[7],
                "E/W": info_list[8],
                "Date": info_list[9],
                "UTC-time": info_list[10],
                "Altitude": info_list[11],
                "Speed": info_list[12],
                "Course": info_list[13],
                "PDOP": info_list[14],
                "HDOP": info_list[15],
                "VDOP": info_list[16],
            }
            return gnss
        else:
            return None

    def getFormattedLatLon(self, gnss: dict):
        """
        Get formatted latitude and longitude from GNSS data.

        :param gnss: Dictionary containing GNSS data
        :return: Tuple of (latitude, longitude) as float values
        """
        if gnss and gnss["Latitude"] != "" and gnss["Longitude"] != "":
            latitude = float(gnss["Latitude"])
            longitude = float(gnss["Longitude"])

            if gnss["N/S"] == "S":
                latitude = -latitude
            if gnss["E/W"] == "W":
                longitude = -longitude
            return latitude, longitude
        else:
            return 0.0, 0.0