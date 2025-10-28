import socket 
import threading
import json
import time

# Host and Port numbers.
HOST = "127.0.0.1"
PORT = 5592

WINDOW_WIDTH = 700
WINDOW_HEIGHT = 700
TANK_WIDTH = 45
TANK_HEIGHT = 30

# Activates the socket server.
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT))  # Sets the server address to the HOST and PORT variables.
server.listen()  # Listening for the client server's input.

# Stores clients into a list.
clients = {}
bullets = []
lock = threading.Lock()
next_id = 1

def client_handling(connection, addr, client_id):
    print(f"Connected: {addr} as ID {client_id}")

    try:
        connection.sendall((json.dumps({"id": client_id}) + "\n").encode())
    except Exception as error:
        print(f"Failed to send ID {addr}: {error}")
    
    with lock:
        clients[connection] = {"id": client_id,"x": 100, "y": 100, "hp": 30}
   
    buffer = ""

    try:
        while True:
            connection.settimeout(0.01)
            try:
                data = connection.recv(4096).decode()
            except socket.timeout:
                data = ""

            if data:
                buffer += data

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError as error:
                        print(f"JSON error from {addr}: {error}, line={line}")
                        continue

                    with lock:
                        if "x" in msg and "y" in msg:
                            clients[connection]["x"] = msg["x"]
                            clients[connection]["y"] = msg["y"]
                        elif msg.get("type") == "bullet":
                            bullets.append(msg["data"])
                        
            delta = 0.02
            with lock:
                message = {"players": list(clients.values()), "bullets": bullets}
                for c in list(clients.keys()):
                    try:
                        c.sendall((json.dumps(message) + "\n").encode())
                    except Exception as error:
                        print(f"Failed to send to client {c}: {error}")
                        c.close()
                        del clients[c]

                for bullet in bullets[:]:
                    bullet["x"] += bullet["vx"] * delta
                    bullet["y"] += bullet["vy"] * delta

                    if (
                        bullet["x"] < 0 or bullet["x"] > WINDOW_WIDTH or 
                        bullet["y"] < 0 or bullet["y"] > WINDOW_HEIGHT
                        ):
                        bullets.remove(bullet)
                        continue
                    

                    for c, player in clients.items():
                        if player["id"] == bullet["owner_id"]:
                            continue
                        if (player["x"] < bullet["x"] < player["x"] + TANK_WIDTH and
                            player["y"] < bullet["y"] < player["y"] + TANK_HEIGHT):

                            player["hp"] -= 10
                            if player["hp"] < 0:
                                player["hp"] = 0
                                
                            print(f"💥 Player {player["id"]} hit by Player {bullet["owner_id"]}")
                            bullets.remove(bullet)
                            break
            with lock:
                 message = {"players": list(clients.values()), "bullets": bullets}
                 for c in list(clients.keys()):
                     try:
                         c.sendall((json.dumps(message) + "\n").encode())
                     except Exception as error:
                         print(f"Failed to send to client {c}: {error}")
                         c.close()
                         del clients[c]

            time.sleep(0.02)
    except Exception as error:
        print(f"Error handling {addr}: {error}")
    finally:
        with lock:
            if connection in clients:
                del clients[connection]
        connection.close()
        print(f"Disconnected from {addr}")

def accept_clients():
    global next_id
    # Status address messages.
    print(f"Game Server is turned on...")
    print(f"Address: {HOST}:{PORT}")

    while True:
        connection, addr = server.accept()
        client_id = next_id
        next_id += 1
        threading.Thread(
            target=client_handling,
            args=(connection, addr, client_id),
            daemon=True
        ).start()

accept_clients()