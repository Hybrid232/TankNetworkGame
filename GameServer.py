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
TANK_WIDTH = 50
TANK_HEIGHT = 50
EXPLOSION_SIZE = (50, 50)
BULLET_RADIUS = 5

# Activates the socket server.
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT)) # Sets the server address to the HOST and PORT.
server.listen()  # Listening for the client server's input.



def generate_walls(num_walls= 8, min_distance= 40):
    walls = []
    
    def rects_overlap(r1, r2, padding=0):
        return not(
            r1["x"] + r1["w"] + padding < r2["x"] or
            r1["x"] > r2["x"] + r2["w"] + padding or
            r1["y"] + r1["h"] + padding < r2["y"] or
            r1["y"] > r2["y"] + r2["h"] + padding
        )
    attempts = 0
    max_attempts = 1000

    while len(walls) < num_walls and attempts < max_attempts:
        attempts += 1

        x = random.randint(50, WINDOW_WIDTH - 150)
        y = random.randint(50, WINDOW_HEIGHT - 150)
        w = random.randint(20, 120)
        h = random.randint(20, 120)


        diagonal = random.choice([True, False])
        
        if diagonal:
            wall = {"x": x, "y": y, "w": w, "h": h, "angle": 45}
        else:
            wall = {"x": x, "y": y, "w": w, "h": h, "angle": 0}

        overlap = False
        for existing in walls:
            if rects_overlap(wall, existing, padding=min_distance):
                overlap = True
                break
        if not overlap:
            walls.append(wall)
    return walls

def reflect_vector(vx, vy, normal_x, normal_y):
    length = (normal_x**2 + normal_y**2) ** 0.5
    nx = normal_x / length
    ny = normal_y / length

    dot = vx * nx + vy * ny

    rx = vx - 2 * dot * nx
    ry = vy - 2 * dot * ny
    return rx, ry


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
                        data = msg["data"]
                        data["bounces"] = 4
                        bullets.append(data)
                        
 # Handle a single client
def client_handling(conn, addr, client_id):
    print(f"Connected: {addr} as ID {client_id}")
    conn.sendall((json.dumps({"id": client_id}) + "\n").encode())
    
    with lock:
        clients[conn] = {"id": client_id, "x": 100, "y": 100, "hp": 30}

    buffer = ""
    while True:
        try:
            conn.settimeout(0.01)
            data = conn.recv(4096).decode()
        except socket.timeout:
            data = ""
        except Exception as e:
            print(f"Client {addr} disconnected: {e}")
            break

        if data:
            buffer += data
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue

                with lock:
                    # Update player position
                    if "x" in msg and "y" in msg:
                        p = clients[conn]
                        p["x"] = msg["x"]
                        p["y"] = msg["y"]

                    # Add bullet
                    elif msg.get("type") == "bullet":
                        bullets.append(msg["data"])
    
    # Remove disconnected client
    with lock:
        if conn in clients:
            del clients[conn]
    conn.close()
    print(f"Disconnected: {addr}")

# Broadcast game state to all clients
def broadcast_state():
    while True:
        with lock:
            state = {
                "players": list(clients.values()),
                "bullets": bullets,
                "walls": walls,
                "explosions": explosions
            }
            for c in list(clients.keys()):
                try:
                    c.sendall((json.dumps(state) + "\n").encode())
                except Exception as e:
                    print(f"Failed to send to client {c}: {e}")
                    c.close()
                    del clients[c]
        time.sleep(0.02)

# Update bullets and handle collisions
def game_tick():
    delta = 0.02
    while True:
        with lock:
            current_time = time.time()
            for bullet in bullets[:]:
                # Move bullet
                bullet["x"] += bullet["vx"] * delta
                bullet["y"] += bullet["vy"] * delta

                bullet_rect = pygame.Rect(bullet["x"], bullet["y"], 5, 5)
                hit_wall = False

                # Wall collision and ricochet
                for wall in walls:
                    wall_rect = pygame.Rect(wall["x"], wall["y"], wall["w"], wall["h"])
                    if bullet_rect.colliderect(wall_rect):
                        hit_wall = True

                        # Previous position
                        prev_x = bullet["x"] - bullet["vx"] * delta
                        prev_y = bullet["y"] - bullet["vy"] * delta
                        prev_rect = pygame.Rect(prev_x, prev_y, 5, 5)

                        # Determine collision normal
                        if prev_rect.right <= wall_rect.left:
                            normal = (-1, 0)
                        elif prev_rect.left >= wall_rect.right:
                            normal = (1, 0)
                        elif prev_rect.bottom <= wall_rect.top:
                            normal = (0, -1)
                        elif prev_rect.top >= wall_rect.bottom:
                            normal = (0, 1)
                        else:
                            normal = (1, 1)

                        # Reflect bullet
                        bullet["vx"], bullet["vy"] = reflect_vector(
                            bullet["vx"], bullet["vy"], normal[0], normal[1]
                        )

                        # Reduce bounces
                        bullet["bounces"] -= 1
                        if bullet["bounces"] <= 0:
                            bullets.remove(bullet)
                        break  # Only bounce once per tick

                if hit_wall:
                    continue  # Skip player collision for this bullet

                # Remove bullets out of bounds
                if (bullet["x"] < 0 or bullet["x"] > WINDOW_WIDTH or
                    bullet["y"] < 0 or bullet["y"] > WINDOW_HEIGHT):
                    bullets.remove(bullet)
                    continue

                # Player collisions
                for player in clients.values():
                    if player["id"] == bullet["owner_id"]:
                        continue
                    if (player["x"] < bullet["x"] < player["x"] + TANK_WIDTH and
                        player["y"] < bullet["y"] < player["y"] + TANK_HEIGHT):

                        player["hp"] -= 10
                        bullets.remove(bullet)

                        if player["hp"] <= 0:
                            explosions.append({
                                "x": player["x"] + TANK_WIDTH // 2 - EXPLOSION_SIZE[0] // 2,
                                "y": player["y"] + TANK_HEIGHT // 2 - EXPLOSION_SIZE[1] // 2,
                                "time": current_time
                            })
                            player["respawn_time"] = current_time + 2.0
                            player["pending_respawn"] = True
                            player["hp"] = 0
                        break  # Stop checking other players for this bullet

            # Delayed respawn
            for player in clients.values():
                if player.get("pending_respawn") and current_time > player["respawn_time"]:
                    player["x"] = random.randint(50, WINDOW_WIDTH - 50)
                    player["y"] = random.randint(50, WINDOW_HEIGHT - 50)
                    player["hp"] = 30
                    player["pending_respawn"] = False

            # Remove old explosions
            explosions[:] = [exp for exp in explosions if current_time - exp["time"] < 1.0]

        time.sleep(delta)


# Accept new clients
def accept_clients():
    global next_id
    print(f"Server running on {HOST}:{PORT}")
    while True:
        conn, addr = server.accept()
        client_id = next_id
        next_id += 1
        threading.Thread(target=client_handling, args=(conn, addr, client_id), daemon=True).start()

# Start threads
threading.Thread(target=game_tick, daemon=True).start()
threading.Thread(target=broadcast_state, daemon=True).start()
accept_clients()