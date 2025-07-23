import time
import re

class HTTP:
    def __init__(self, outer):
        """
        Initialize HTTP object.

        :param outer: Reference to outer class (likely modem controller)
        """
        self.outer = outer

    class HTTPRequest:
        """
        Enum-like class for HTTP request methods.
        """
        GET = "0"
        POST = "1"
        HEAD = "2"
        DELETE = "3"
        PUT = "4"

    def InternetConnection(self, debug: bool = False):
        """
        Check if there's an active internet connection.

        :param debug: Enable debug output
        :return: Boolean indicating if there's an active internet connection
        """
        try:
            pdp_status = self.outer.SendAT("AT+CGACT?", 2, "+CGACT:", debug)
            return "+CGACT: 1,1" in pdp_status
        except Exception:
            return False

    def __startHTTPRequest(self, method: str, debug=False):
        """
        Start an HTTP request.

        :param method: HTTP method to use
        :return: List of response parameters or None if failed
        """
        temp = self.outer.SendAT("AT+HTTPACTION=" + method, 1, "OK", debug=debug)
        if "ERROR" in temp:
            print("HTTPACTION Error")
            time.sleep(0.2)
            return None
        
        temp = ""
        for _ in range(121):
            temp += self.outer.ReadSerial(1, debug=debug)
            if "ACTION:" in temp and temp.endswith("\n"):
                time.sleep(0.2)
                return list(map(int, re.findall(r"\d+", temp)))
        return None

    def SendHTTPRequest(self, URL: str, method: str = HTTPRequest.GET, data: str = None, chunk_size:int = 256, debug=False):
        """
        Send an HTTP request.

        :param URL: The URL to send the request to
        :param method: HTTP method to use (default is GET)
        :param data: Data to send with the request (for POST/PUT)
        :param debug: Enable debug output
        :return: HTTP response code or False if request failed
        """
        try:
            if "ERROR" in self.outer.SendAT("AT+HTTPINIT", 1, debug=debug):
                print("Error initializing HTTP server")
                time.sleep(0.2)
                self.terminateHTTP(debug)
                return False

            time.sleep(0.2)
            self.outer.SendAT(f'AT+HTTPPARA="URL","{URL}"', 1, debug=debug)
            time.sleep(0.2)

            if data:
                time.sleep(0.2)
                self.outer.SendAT(f"AT+HTTPDATA={len(data)},5000", 5, "DOWNLOAD", debug)
                
                if debug:
                    print(data)
                
                time.sleep(0.2)
                for i in range(0, len(data), chunk_size):
                    chunk = data[i:i+chunk_size]
                    if debug:
                        print(f"\n\nSent chunk: {chunk} \n\n")
                    self.outer.ser.write(chunk.encode())
                    time.sleep(0.2)
                self.outer.ReadSerial(5, "OK", debug)
                time.sleep(3)

            HTTPResponse = self.__startHTTPRequest(method, debug=debug)
            if not HTTPResponse:
                print("Error Sending Request to the server")
                #self.terminateHTTP(debug)
                return False

            return HTTPResponse
        except Exception as e:
            print(f"Exception occurred: {str(e)}")
            import traceback
            traceback.print_exc()
            self.terminateHTTP(debug)
            raise KeyboardInterrupt
    
    def ReadHTTPHeader(self, waittime: int = 1, debug: bool = False):
        """
        Reads the HTTP headers from the server response.

        :param waittime: Time to wait for the response in seconds. Default is 1.
        :param debug: Enables debug mode if True. Default is False.
        :return: The HTTP headers from the response.
        """
        return self.outer.SendAT("AT+HTTPHEAD", waittime, debug=debug)

    def ReadHTTPResponse(self, length: int, waittime: int = 1, debug: bool = False):
        """
        Reads the HTTP body/content from the server response.

        :param length: Number of bytes to read.
        :param waittime: Time to wait for the response in seconds. Default is 1.
        :param debug: Enables debug mode if True. Default is False.
        :return: The HTTP body from the response.
        """
        return self.outer.SendAT(f"AT+HTTPREAD=0,{length}", waittime, debug=debug)

    def terminateHTTP(self, debug = False):
        """
        Terminate the HTTP connection.

        :param debug: Enable debug output
        """
        print("Terminating the HTTP connection")
        self.outer.SendAT("AT+HTTPTERM", 1, debug=debug)
        time.sleep(3)