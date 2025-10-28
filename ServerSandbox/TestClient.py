import socket

# Matches server settings.
HOST = "127.0.0.1"
PORT = 65432

# Creats the socket just like the server. 
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:

    # Client connects or "calls" the server with the settings.
    s.connect((HOST, PORT))

    # Sends bytes to the server.
    # Strings must be turned into bytes first.
    s.sendall(b"Hello, from the other siiiiide")

    # Waits to reveive the servers response (up to 1024 bytes).
    data = s.recv(1024)

# Converts the bytes to text and prints the reply.
print(f"Recived {data!r}")

