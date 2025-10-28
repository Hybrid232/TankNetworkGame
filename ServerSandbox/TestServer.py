import socket

HOST = "127.0.0.1" # Standard loopback address.
PORT = 65432 # Port Number (lets multiple networks coexist on one divice)

# socket.AF_INET means we are using the IPv4 (HOST address)
# socket.SOCKSTREAM means we are using TCP (reliable connection-based protocol)
# with makes sure the socket closes automatically when finished.
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:

    # Makes sure that no other networks connect to this program.
    # Tells the OS: "Send all traffic to 127.0.0.1:65432 to this program".
    s.bind((HOST, PORT))

    # Listening for connection requests / waiting for clients
    s.listen()

    # Status Message.
    print(f"Server is listening on {HOST}:{PORT}")

    # Waits until client has connected.
    # conn = new socket object to talk direclty to client.
    # addr = client's address (IP + port)
    # Server picks up the phone -- can talk directly to the caller.
    conn, addr = s.accept()

    # Another with statment to make sure the client's connection closes
    # when finished.
    with conn:
        print(f"Connected by {addr}")

        # Waits to receive up to 1024 bytes from client.
        # This blocks data until the data arrives.
        # Client sends "Hello, world", data becomes b"Hello, World".
        while True:
            data = conn.recv(1024)

            # If no data revieved, exit loop
            if not data:
                break

            # Send data back to client (an echo)
            conn.sendall(data)

