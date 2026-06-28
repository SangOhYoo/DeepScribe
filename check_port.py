import socket
s = socket.socket()
s.settimeout(1)
res = s.connect_ex(('127.0.0.1', 7862))
print(f"Port 7862 status: {res}")
s2 = socket.socket()
s2.settimeout(1)
res2 = s2.connect_ex(('127.0.0.1', 8081))
print(f"Port 8081 status: {res2}")
