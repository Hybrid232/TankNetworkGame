import socket 
import threading
import json
import time
import random
import pygame

# Host and Port numbers.
# 0.0.0.0 binds to all interfaces
# 192.168.1.45 will bind to this specific LAN IP 

HOST = "127.0.0.1"
# HOST = "0.0.0.0" 
PORT = 5592

WINDOW_WIDTH = 700
WINDOW_HEIGHT = 700
TANK_WIDTH = 45
TANK_HEIGHT = 30
EXPLOSION_SIZE = (50, 50)

# Activates the socket server.
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT)) # Sets the server address to the HOST and PORT.
server.listen()  # Listening for the client server's input.


def generate_walls(num_walls=6):
    walls = []
    for _ in range(num_walls):
        x = random.randint(50, WINDOW_WIDTH - 150)
        y = random.randint(50, WINDOW_HEIGHT - 150)
        w = random.randint(60, 250)
        h = random.randint(20, 40)
        walls.append({"x": x, "y": y, "w": w, "h": h})
    return walls

# Stores clients into a dictionary.
clients = {}
bullets = []
explosions = []
lock = threading.Lock()
next_id = 1
walls = generate_walls()

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
                            p = clients[connection]

                            if "respawn_time" not in p or time.time() - \
                            p["respawn_time"] > 0.5:
                                p["x"] = msg["x"]
                                p["y"] = msg["y"]
                                
                        elif msg.get("type") == "bullet":
                            bullets.append(msg["data"])
                        
            delta = 0.02
         
            with lock:
                for bullet in bullets[:]:
                    # Update bullets.
                    bullet["x"] += bullet["vx"] * delta
                    bullet["y"] += bullet["vy"] * delta

                    bullet_rect = pygame.Rect(bullet["x"], bullet["y"], 5,5)
                    hit_wall = False
                    for wall in walls:
                        wall_rect = pygame.Rect(wall["x"], wall["y"],
                                                wall["w"], wall["h"])
                        if bullet_rect.colliderect(wall_rect):
                            bullets.remove(bullet)
                            hit_wall = True
                            break
                    if hit_wall:
                        continue

                    # Remove bullets out of bounds.
                    if (
                        bullet["x"] < 0 or bullet["x"] > WINDOW_WIDTH or 
                        bullet["y"] < 0 or bullet["y"] > WINDOW_HEIGHT
                        ):
                        bullets.remove(bullet)
                        continue
                    
                    # Bullet hit's player functions.
                    for c, player in clients.items():
                        if player["id"] == bullet["owner_id"]:
                            continue
                        if (player["x"] < bullet["x"] < player["x"] 
                            + TANK_WIDTH and 
                            player["y"] < bullet["y"] < player["y"] 
                            + TANK_HEIGHT):

                            player["hp"] -= 10
                            if player["hp"] < 0:
                                player["hp"] = 0

                            print(f"💥 Player {player["id"]} \
                                  hit by Player {bullet["owner_id"]}")
                            bullets.remove(bullet)
                            if player["hp"] <= 0:
                                explosions.append({
                                    "x": player["x"] + TANK_WIDTH//2
                                      - EXPLOSION_SIZE[0]//2,
                                    "y": player["y"] + TANK_HEIGHT//2
                                      - EXPLOSION_SIZE[1]//2,

                                    "time": time.time()
                                })
                                # mark player for delayed respawn
                                player["respawn_time"] = time.time() + 2.0
                                player["pending_respawn"] = True
                            break
            
            # Delayed Respawn Handling.
            for player in clients.values():
                if player.get("pending_respawn") and time.time() \
                > player["respawn_time"]:
                    player["x"] = random.randint(50, WINDOW_WIDTH - 50)
                    player["y"] = random.randint(50, WINDOW_HEIGHT - 50)
                    player["hp"] = 30
                    player["pending_respawn"] = False
            
                           
            current_time = time.time()
            explosions[:] = [exp for exp in explosions if current_time
                             - exp["time"] < 1.0]
        
            # Sends game info to client.
            with lock:
                 message = {"players": list(clients.values()),
                            "bullets": bullets,
                            "walls": walls,
                            "explosions": explosions}
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


# 
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