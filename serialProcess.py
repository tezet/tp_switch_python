import serial
import time
import multiprocessing

class SerialProcess(multiprocessing.Process):

    def __init__(self, taskQ, resultQ, msg_op):
        multiprocessing.Process.__init__(self)
        self.taskQ = taskQ
        self.resultQ = resultQ
        #self.usbPort = '/dev/ttyATH0'
        #self.usbPort='/dev/tty.serial1'
        self.usbPort = '/dev/ttyUSB0'
        self.sp = serial.Serial(self.usbPort, 115200, timeout=1)
        self.msg_op = msg_op

    def close(self):
        self.sp.close()

    def sendData(self, data):
        self.sp.write(str(data))
        print "sendData: " + data

    def run(self):

        self.sp.flushInput()

        while True:
            # look for incoming tornado request
            if not self.taskQ.empty():
                msg = self.taskQ.get()

                msg = str(msg)
                # send it to the mcu
                self.sp.write(msg + "\n");
                print "msg to mcu: " + msg

            result = self.sp.readline()

            # send it back to tornado
            if result <> "":
                self.resultQ.put(dict(op=self.msg_op, msg=result))

