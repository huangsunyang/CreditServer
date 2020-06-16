import Queue
import struct


class IterableQueue(Queue.Queue):
    def pop(self):
        if self.empty():
            return None
        return self.get_nowait()

    def __iter__(self):
        return iter(self.pop, None)


# data is btyes
def get_sid(data):
    assert len(data) >= 4
    sid_byte = data[0:4]
    return struct.unpack('I', sid_byte)[0]


# decode
def decode(data):
    return data


# encode
def encode(obj):
    return obj
