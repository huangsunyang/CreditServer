import socket
import random
from net.net_utils import encode
from net.net_utils import IterableQueue
from net.netstream import NetStream, conf


class NetworkError(Exception):
    def __init__(self, msg):
        super(NetworkError, self).__init__(msg)


class HidLookUpError(NetworkError):
    def __init__(self, msg):
        super(HidLookUpError, self).__init__(msg)


class Network(object):
    def __init__(self, timeout=conf.NET_HOST_DEFAULT_TIMEOUT):
        super(Network, self).__init__()

        self.hid_to_client = {}  # type: dict{int, NetStream or socket.socket}
        self.error_socks = set()

        self.queue = IterableQueue()
        self.sock = None
        self.port = 0
        self.timeout = timeout
        self.state = conf.SOCK_STATE_STOP

        return

    # a random/unique hid for each client
    def generate_id(self):
        hid = random.randint(0, 10000)
        while hid in self.hid_to_client:
            hid = random.randint(0, 10000)
        return hid

    # bind and listen, ready for accept
    def startup(self, port=0):
        self.shut_down()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.sock.bind(('0.0.0.0', port))
        except socket.error:
            try:
                self.sock.close()
            except socket.error, err_msg:
                print(err_msg)
            return

        self.hid_to_client[-1] = self.sock  # -1 reserved for server socket

        self.sock.listen(socket.SOMAXCONN)  # determined by SOMAXCONN
        self.sock.setblocking(0)

        self.port = self.sock.getsockname()[1]
        self.state = conf.SOCK_STATE_CONNECTED

    # stop transmitting, close all sockets
    def shut_down(self):
        for client in self.hid_to_client.itervalues():
            client.close()

        self.hid_to_client = {}
        self.queue = IterableQueue()
        self.state = conf.SOCK_STATE_STOP

    def get_client(self, hid):
        assert hid >= 0

        # client already offline
        if hid not in self.hid_to_client:
            print("client:" + str(hid) + " already offline, send data failed")
            return None

        client = self.hid_to_client[hid]
        if client is None or client.hid != hid:
            raise HidLookUpError("client hid not match")
        return client

    def add_client(self, hid, client):
        if hid in self.hid_to_client:
            raise HidLookUpError("client already exists")
        self.hid_to_client[hid] = client

    # upper close client connection, no event sent any more
    def close_client(self, hid):
        # remove from the hid->client dict
        client = self.get_client(hid)
        if client is not None:
            self.error_socks.add(client)

    # get and send
    def send_data(self, hid, data):
        client = self.get_client(hid)

        if client is not None:
            client.send_bytes(data)

    def send_object(self, hid, obj):
        data = encode(obj)
        self.send_data(hid, data)

    def broadcast_object(self, hid_list, obj):
        data = encode(obj)
        for hid in hid_list:
            self.send_data(hid, data)

    def broadcast_object_list(self, hid_list, obj_list):
        for obj in obj_list:
            self.broadcast_object(hid_list, obj)

    def client_nodelay(self, hid, nodelay=0):
        """
        set tcp_nodelay option for specific client
        which means not waiting for filling send buffer in socket before sending
        """
        client = self.get_client(hid)

        if client is not None:
            return client.nodelay(nodelay)

    # import method from another file, since this file is too large
    from net.handle_events import update
    from net.handle_events import handle_events
    from net.handle_events import handle_read_events
    from net.handle_events import handle_write_events
    from net.handle_events import handle_timeout_events
    from net.handle_events import handle_new_client
    from net.handle_events import clean_error_socks
    from net.handle_events import recv_data_from_client


network = Network()

if __name__ == '__main__':
    network.startup(port=8888)

    while True:
        network.update()
