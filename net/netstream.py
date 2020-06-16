import sys
import socket
import struct
import errno

class conf(object):
    SOCK_STATE_STOP = 1
    SOCK_STATE_CONNECTING = 2
    SOCK_STATE_CONNECTED = 3

    SOCK_CAN_READ = 1 << 0
    SOCK_CAN_WRITE = 1 << 1

    NET_HEAD_LENGTH_SIZE = 4
    NET_HEAD_LENGTH_FORMAT = '<I'  # little endian, unsigned int
    NET_HOST_DEFAULT_TIMEOUT = 30
    NET_PACKET_MAX_SIZE = 1024 * 16

    NET_CONNECTION_NONE = -1
    NET_CONNECTION_NEW = 0
    NET_CONNECTION_DATA = 1
    NET_CONNECTION_LEAVE = 2


class BytesBuffer(object):
    def __init__(self):
        self.content = ''

    def empty(self):
        return bool(self.content)

    def getAll(self):
        return self.content

    def popLeftN(self, n):
        ret = self.content[0:n]
        self.content = self.content[n:]
        return ret

    def pushRight(self, s):
        self.content += s

    def __len__(self):
        return len(self.content)


class NetStream(object):
    """
    manage a single socket to a single client

    send_bytes: add to send_buf
    recv_bytes: retrieve from recv_buf
    _try_send_buffer: send from send_buf to socket
    _try_recv_from_sock: recv from socket into recv_buf
    """

    def __init__(self):
        super(NetStream, self).__init__()

        self.sock = None

        self._send_buf = BytesBuffer()
        self._recv_buf = BytesBuffer()
        self._state = conf.SOCK_STATE_STOP

        self._errd = (errno.EINPROGRESS, errno.EALREADY, errno.EWOULDBLOCK)
        self._conn = (errno.EISCONN, 10057, 10053)
        self._errc = 0
        self._cur_packet_size = -1

    @property
    def state(self):
        return self._state

    def fileno(self):
        return self.sock.fileno()

    def connect(self, address, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setblocking(0)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

        self.sock.connect((address, port))
        self._state = conf.SOCK_STATE_CONNECTING

    def close(self):
        self._state = conf.SOCK_STATE_STOP

        if self.sock is None:  # already closed
            return

        try:
            self.sock.close()
        except socket.error, err_info:
            print err_info

        self.sock = None

    def assign_sock(self, sock):
        self.close()
        self.sock = sock
        self.sock.setblocking(0)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        self._state = conf.SOCK_STATE_CONNECTED

        self._send_buf = BytesBuffer()
        self._recv_buf = BytesBuffer()

    def nodelay(self, nodelay=0):
        if 'TCP_NODELAY' not in socket.__dict__:
            return -1
        if self._state != conf.SOCK_STATE_CONNECTED:
            return -2

        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, nodelay)
        return 0

    def try_connect(self):
        if self._state == conf.SOCK_STATE_CONNECTED:
            return 1
        elif self._state != conf.SOCK_STATE_CONNECTING:
            return -1

        try:
            self.sock.recv(0)
        except socket.error, (code, error_msg):
            if code in self._conn:
                return 0
            elif code in self._errd:
                self._state = conf.SOCK_STATE_CONNECTED
                self._recv_buf = BytesBuffer()
                return 1

            self.close()
            return -1

        self._state = conf.SOCK_STATE_CONNECTED
        return 1

    # add packet size header and call send_raw
    def send_bytes(self, data):
        total_size = len(data) - 4
        size_head = struct.pack(conf.NET_HEAD_LENGTH_FORMAT, total_size)

        self._send_raw(size_head + data)

    def _send_raw(self, data):
        self._send_buf.append(data)

    def _try_send_buffer(self):
        if self._send_buf.empty():
            return

        sent_size = 0

        try:
            sent_size = self.sock.send(self._send_buf.getAll())
        except socket.error, (code, error_msg):
            if code not in self._errd:
                self._errc = code
                raise

        self._send_buf.popLeftN(sent_size)
        return sent_size

    def recv_bytes(self):
        print self._recv_buf.content
        self._recv_buf.content = ""
        return
        # no packet_size in buffer, try get packet size info
        if self._cur_packet_size < 0:

            # can not get size header
            if len(self._recv_buf) < conf.NET_HEAD_LENGTH_SIZE:
                return ''

            head_length_byte = self._recv_buf.popLeftN(conf.NET_HEAD_LENGTH_SIZE)

            self._cur_packet_size = struct.unpack(conf.NET_HEAD_LENGTH_FORMAT, head_length_byte)[0]

            if self._cur_packet_size > conf.NET_PACKET_MAX_SIZE:
                raise socket.error(-1, "packet size out of limit")

        # can not get all data
        if len(self._recv_buf) < self._cur_packet_size + 4:
            return ''

        # success, reset _cur_packet_size
        data = self._recv_buf.popLeftMaxN(self._cur_packet_size + 4)

        self._cur_packet_size = -1
        return data

    def _try_recv_from_sock(self):
        once_size = 1024
        recv_buffer = BytesBuffer()

        while True:
            once_recv = ''
            try:
                once_recv = self.sock.recv(once_size)
                if not once_recv:
                    raise socket.error(-1, "dead connection")

            except socket.error, (code, error_msg):
                if code not in self._errd:
                    self.errc = code
                    raise

            if once_recv == '':
                break
            else:
                print('recv bytes', repr(once_recv))
                recv_buffer.pushRight(once_recv)
        self._recv_buf.pushRight(recv_buffer.getAll())
        return len(recv_buffer)

    def process(self, rw=conf.SOCK_CAN_READ | conf.SOCK_CAN_WRITE):
        if self._state == conf.SOCK_STATE_STOP:
            return
        if self._state == conf.SOCK_STATE_CONNECTING:
            self.try_connect()
        if self._state == conf.SOCK_STATE_CONNECTED and rw & conf.SOCK_CAN_READ > 0:
            self._try_recv_from_sock()
        if self._state == conf.SOCK_STATE_CONNECTED and rw & conf.SOCK_CAN_WRITE > 0:
            self._try_send_buffer()


# unit test
if __name__ == '__main__':
    pass
