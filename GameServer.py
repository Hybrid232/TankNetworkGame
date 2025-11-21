import socket
import threading
import json
import time
import random
import pygame

# Server settings
HOST = "127.0.0.1"
PORT = 5592

# Game window and tank constants
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 790
TANK_WIDTH = 50
TANK_HEIGHT = 50
EXPLOSION_SIZE = (50, 50)
BULLET_RADIUS = 5
MAX_PLAYERS = 4

# Spawn points (corners)
SPAWN_POINTS = [
    (50, 50),  # TOP LEFT
    (WINDOW_WIDTH - 50 - TANK_WIDTH, 50),  # TOP RIGHT
    (50, WINDOW_HEIGHT - 50 - TANK_HEIGHT),  # BOTTOM LEFT
    (WINDOW_WIDTH - 50 - TANK_WIDTH, WINDOW_HEIGHT - 50 - TANK_HEIGHT)  # BOTTOM RIGHT
]

# Socket setup
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT))
server.listen()

# Game state
clients = {}
bullets = []
explosions = []
lock = threading.Lock()
next_id = 1

# Generate walls
def generate_walls(num_walls=16, min_distance=45):
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
        x = random.randint(20, WINDOW_WIDTH - 180)
        y = random.randint(20, WINDOW_HEIGHT - 180)
        w = random.randint(100, 120)
        h = random.randint(10, 100)
        diagonal = random.choice([True, False])
        wall = {"x": x, "y": y, "w": w, "h": h, "angle": 45 if diagonal else 0}
        overlap = any(rects_overlap(wall, w2, padding=min_distance) for w2 in walls)
        if not overlap:
            walls.append(wall)
    return walls

walls = generate_walls()

# Bullet reflection
def reflect_vector(vx, vy, nx, ny):
    length = (nx**2 + ny**2) ** 0.5
    nx /= length
    ny /= length
    dot = vx * nx + vy * ny
    rx = vx - 2 * dot * nx
    ry = vy - 2 * dot * ny
    return rx, ry

#  SPAWN LOGIC 

def get_free_spawn_slot():
    """Return a free corner index (0-3) not occupied by active players."""
    occupied = {p.get("spawn_slot") for p in clients.values() if not p.get("pending_respawn")}
    for i in range(MAX_PLAYERS):
        if i not in occupied:
            return i
    return 0  # fallback

# CLIENT HANDLING 

def client_handling(connection, addr, client_id):
    print(f"Connected: {addr} as ID {client_id}")
    try:
        connection.sendall((json.dumps({"id": client_id}) + "\n").encode())
    except Exception as e:
        print(f"Failed to send ID: {e}")

    with lock:
        if len(clients) >= MAX_PLAYERS:
            connection.sendall((json.dumps({"error": "Server full!"}) + "\n").encode())
            connection.close()
            return

        slot = get_free_spawn_slot()
        spawn_x, spawn_y = SPAWN_POINTS[slot]
        clients[connection] = {
            "id": client_id,
            "x": spawn_x,
            "y": spawn_y,
            "hp": 30,
            "spawn_slot": slot,
            "spawn_protect_time": time.time() + 1.0
        }

    buffer = ""
    while True:
        try:
            connection.settimeout(0.01)
            data = connection.recv(4096).decode()
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
                    # Player movement update
                    if "x" in msg and "y" in msg:
                        p = clients[connection]
                        if time.time() > p.get("spawn_protect_time", 0):
                            p["x"] = msg["x"]
                            p["y"] = msg["y"]

                    # Bullet creation
                    elif msg.get("type") == "bullet":
                        bullets.append(msg["data"])

    with lock:
        if connection in clients:
            del clients[connection]
    connection.close()
    print(f"Disconnected: {addr}")

# GAME BROADCAST 

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
                except:
                    c.close()
                    if c in clients:
                        del clients[c]
        time.sleep(0.02)

# GAME TICK

def game_tick():
    delta = 0.02
    while True:
        with lock:
            current_time = time.time()

            # Update bullets
            for bullet in bullets[:]:
                bullet["x"] += bullet["vx"] * delta
                bullet["y"] += bullet["vy"] * delta
                bullet_rect = pygame.Rect(bullet["x"], bullet["y"], 5, 5)

                # Wall collision
                for wall in walls:
                    wall_rect = pygame.Rect(wall["x"], wall["y"], wall["w"], wall["h"])
                    if bullet_rect.colliderect(wall_rect):
                        # Reflect bullet
                        prev_x = bullet["x"] - bullet["vx"] * delta
                        prev_y = bullet["y"] - bullet["vy"] * delta
                        prev_rect = pygame.Rect(prev_x, prev_y, 5, 5)
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

                        bullet["vx"], bullet["vy"] = reflect_vector(
                            bullet["vx"], bullet["vy"], normal[0], normal[1]
                        )
                        bullet["bounces"] -= 1
                        if bullet["bounces"] <= 0:
                            bullets.remove(bullet)
                        break

                if bullet["x"] < 0 or bullet["x"] > WINDOW_WIDTH or bullet["y"] < 0 or bullet["y"] > WINDOW_HEIGHT:
                    bullets.remove(bullet)
                    continue

                # Player collision
                for player in clients.values():
                    if player["id"] == bullet["owner_id"]:
                        continue
                    if (player["x"] < bullet["x"] < player["x"] + TANK_WIDTH and
                        player["y"] < bullet["y"] < player["y"] + TANK_HEIGHT):
                        player["hp"] -= 10
                        bullets.remove(bullet)
                        if player["hp"] <= 0:
                            explosions.append({
                                "x": player["x"] + TANK_WIDTH//2 - EXPLOSION_SIZE[0]//2,
                                "y": player["y"] + TANK_HEIGHT//2 - EXPLOSION_SIZE[1]//2,
                                "time": current_time
                            })
                            player["respawn_time"] = current_time + 2.0
                            player["pending_respawn"] = True
                            player["hp"] = 0
                        break

            # Handle respawns
            for player in clients.values():
                if player.get("pending_respawn") and current_time > player["respawn_time"]:
                    slot = get_free_spawn_slot()
                    spawn_x, spawn_y = SPAWN_POINTS[slot]
                    player["x"], player["y"] = spawn_x, spawn_y
                    player["hp"] = 30
                    player["pending_respawn"] = False
                    player["spawn_slot"] = slot
                    player["spawn_protect_time"] = current_time + 1.0

            # Remove old explosions
            explosions[:] = [e for e in explosions if current_time - e["time"] < 1.0]

        time.sleep(delta)

# CLIENT ACCEPT LOOP 

def accept_clients():
    global next_id
    print(f"Server running on {HOST}:{PORT}")
    while True:
        conn, addr = server.accept()
        client_id = next_id
        next_id += 1
        threading.Thread(target=client_handling, args=(conn, addr, client_id), daemon=True).start()

# START THREADS 

threading.Thread(target=game_tick, daemon=True).start()
threading.Thread(target=broadcast_state, daemon=True).start()
accept_clients()
