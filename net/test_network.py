# -*- coding: utf-8 -*-
import socket


class TestClient(object):
	def __init__(self):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.sock.connect_ex(('127.0.0.1', 8888))
		self.sock.send('0000')


if __name__ == '__main__':
	a = TestClient()
