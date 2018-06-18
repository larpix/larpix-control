import zmq
import time

class CommandReceiver(object):
    '''Accepts commands from ZMQ sockets, sends packets to LArPix, and
    forwards on the received LArPix packets back out over ZMQ.

    '''

    def __init__(self, port):
        self.port = port
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.connect(self.port)

    def run(self):
        '''Event loop:

            - Wait for a request

            - If the request contains a timeout longer than 0, begin
              listening to packets from LArPix

            - If the request contains a bytestream to write out (2nd
              frame), write it out immediately

            - When the timeout expires (or if it is 0):
                - stop listening (skip this step if timeout == 0)
                - send a reply containing all of the bytes received from
                  LArPix (or an empty bytestream if none received or if 0
                  timeout).
        '''
        try:
            while(True):
                print('Awaiting command')
                timeout, bytes_to_write = self.socket.recv_multipart()
                print('Received command')

                timeout = float(timeout)
                start_time = time.time()
                if timeout > 0:
                    self.begin_listening_to_LArPix()
                if len(bytes_to_write) > 0:
                    self.write_to_LArPix(bytes_to_write)
                now = start_time
                while now < start_time + timeout:
                    time.sleep(0.01)
                    now = time.time()
                new_bytes = None
                if timeout > 0:
                    new_bytes = self.retrieve_LArPix_bytes()
                else:
                    new_bytes = b''
                self.stop_listening_to_LArPix()

                print('Sending response')
                self.socket.send(new_bytes)
                print('Sent response')
        except KeyboardInterrupt:
            return

    def begin_listening_to_LArPix(self):
        '''Dummy method modelling opening a serial port for reading.

        '''
        pass

    def write_to_LArPix(self, to_write):
        '''Dummy method modelling writing out bytes to serial UART
        or similar protocol.

        '''
        print(to_write)
        return

    def stop_listening_to_LArPix(self):
        '''Dummy method modelling closing a serial port.

        '''
        pass

    def retrieve_LArPix_bytes(self):
        '''Dummy method modelling reading bytes from serial UART or
        similar protocol.

        '''
        python3 = False
        try:
            get_input = raw_input
        except:
            python3 = True
            get_input  = input

        message = get_input('Enter bytestream: ')
        if python3:
            message = bytes(message, encoding='raw_unicode_escape')
        return message
