import select
import socket
import time
from net.net_utils import decode
from net.netstream import NetStream, conf


def update(self):
    """
    main update of network
    detect events of client(read/write/data) and add to event queue
    """
    if self.state != conf.SOCK_STATE_CONNECTED:
        return

    self.handle_events()


def handle_events(self):
    """
    detect and handle events
    """
    read_socks, write_socks, _ = select.select(
        self.hid_to_client.itervalues(),
        self.hid_to_client.itervalues(),
        [], 0
    )

    self.handle_read_events(read_socks)
    self.handle_write_events(write_socks)
    self.handle_timeout_events()
    self.clean_error_socks()


def handle_read_events(self, read_socks):
    """
    decide if sock is for accept new connection or new data
    """
    for client in read_socks:
        if client == self.sock:
            self.handle_new_client()
        else:
            self.recv_data_from_client(client)


def handle_new_client(self):
    """
    new connection comes
    """
    sock = None

    try:
        sock, remote = self.sock.accept()
        sock.setblocking(0)
    except socket.error, (code, err_msg):
        if code != 10035:  # nonblocking err msg on windows
            print(err_msg)
        return

    hid = self.generate_id()

    client = NetStream()
    client.assign_sock(sock)
    client.hid = hid
    client.active = time.time()
    client.peername = sock.getpeername()

    self.hid_to_client[hid] = client
    print 'new client {}'.format(hid)
    self.queue.put_nowait(
        (conf.NET_CONNECTION_NEW, hid, repr(client.peername)))


def recv_data_from_client(self, client):
    """
    if sock can read, try retrieve data from socket to its buffer in memory
    then try decode packet from the receive buffer in memory
    """
    try:
        client.process(rw=conf.SOCK_CAN_READ)
    except socket.error, (code, err_msg):
        self.error_socks.add(client)
        return

    while client.state == conf.SOCK_STATE_CONNECTED:
        data = client.recv_bytes()
        if data == '':
            break

        # client may send incompatible packets
        try:
            self.queue.put_nowait(
                (conf.NET_CONNECTION_DATA, client.hid, decode(data)))
        except:
            print('error in decode:', client.hid)
            self.error_socks.add(client)

        client.active = time.time()


def handle_write_events(self, write_socks):
    """
    if socket can write, try send the data in write buffer
    """
    for client in write_socks:
        try:
            client.process(rw=conf.SOCK_CAN_WRITE)
        except socket.error, (code, err_msg):
            self.error_socks.add(client)


def handle_timeout_events(self):
    """
    if client not sending packet for some time, close the connection
    """
    cur_time = time.time()
    for hid, client in self.hid_to_client.iteritems():
        if hid >= 0 and cur_time - client.active > self.timeout:
            print('disconnect for timeout', client.hid)
            self.error_socks.add(client)


def clean_error_socks(self):
    """
    close all the sockets that throw exception when reading or writing
    """
    for client in self.error_socks:
        self.queue.put_nowait(
            (conf.NET_CONNECTION_LEAVE, client.hid, repr(client.peername)))

        del self.hid_to_client[client.hid]
        print 'lose client {}'.format(client.hid)
        client.close()

    self.error_socks.clear()
