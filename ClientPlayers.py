import socket
import threading 
import pygame 
import json
import time

HOST = "127.0.0.1"
PORT = 5592

# Opens the server for the client.
client_player = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Takes 5 seconds for program to develop and connect.
client_player.settimeout(5.0) 
 
# Attempts to connect, and closes program if connection failed.
try:
    client_player.connect((HOST, PORT))
except Exception as error:
    print("Failed to connect to server:", error)
    client_player.close()
    exit()

buffer = ""
data = None
for attempt in range(5):
    try:
        chunk = client_player.recv(4096).decode()
        if not chunk:
            continue
        buffer += chunk
        if "\n" in buffer:
            data, buffer = buffer.split("\n", 1) 
            break
    except socket.timeout:
        continue
    except Exception as error:
        print(f"Error while receiving ID: {error}")
        client_player.close()
        exit()

my_id = json.loads(data)["id"]
print(f"Connected as player ID {my_id}")
client_player.settimeout(0.1)

# Initialize Pygame.
pygame.init()

BORDER_THICKNESS = 10
WINDOW_WIDTH = 700
WINDOW_HEIGHT = 700
TANK_WIDTH = 45
TANK_HEIGHT = 30

screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("Multiplayer Tank Game")
clock = pygame.time.Clock()
dt = 0

tank_player = {"x": 250, "y": 200}
others = []
bullets = []
cursor = pygame.cursors.Cursor(pygame.SYSTEM_CURSOR_CROSSHAIR) 

last_shot_time = 0
shot_cooldown = 1


buffer = ""

def recieve_thread():
    global others, bullets, buffer
    while True:
        try:
            data = client_player.recv(4096).decode()
            if not data:
                print("Server disconnected")
                continue
            buffer += data

            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                try:
                    msg = json.loads(line)
                    others = [p for p in msg.get("players", []) if p.get("id") != my_id]
                   
                    for p in msg.get("players", []):
                        if p.get("id") == my_id:
                            player_health.hp = p.get("hp", 30)
                    
                    bullets = msg.get("bullets", [])
                except json.JSONDecodeError as error:
                    print(f"JSON error in recieve_thread function: {error}, line={line}")

        except socket.timeout:
            continue
        except Exception as error:
            print(f"Receive thread connection error: {error}")
            break

threading.Thread(target=recieve_thread, daemon=True).start()


def player_movement():
    keys = pygame.key.get_pressed()
    if keys[pygame.K_w]:
        tank_player["y"] -= 150 * dt
    if keys[pygame.K_s]:
        tank_player["y"] += 150 * dt
    if keys[pygame.K_d]:
        tank_player["x"] += 150 * dt
    if keys[pygame.K_a]:
        tank_player["x"] -= 150 * dt

    tank_player["x"] = max(BORDER_THICKNESS, min(tank_player["x"],
                                    WINDOW_WIDTH - BORDER_THICKNESS - TANK_WIDTH))
    tank_player["y"] = max(BORDER_THICKNESS, min(tank_player["y"], 
                                    WINDOW_HEIGHT - BORDER_THICKNESS - TANK_HEIGHT))

def player_fire(mouse_x, mouse_y):
    global last_shot_time
    current_time = time.time()
    if current_time - last_shot_time < shot_cooldown:
        return
    last_shot_time = current_time

    bullet = {
        "x": tank_player["x"] + TANK_WIDTH // 2,
        "y": tank_player["y"] + TANK_HEIGHT // 2,
        "vx": 0,
        "vy": 0,
        "owner_id": my_id
    }

    dx = mouse_x - (tank_player["x"] + TANK_WIDTH // 2)
    dy = mouse_y - (tank_player["y"] + TANK_HEIGHT // 2)
    distance = (dx**2 + dy**2)**0.5
    if distance == 0:
        return
    
    speed = 500

    bullet["vx"] = dx / distance * speed
    bullet["vy"] = dy / distance * speed

    try:
        msg = json.dumps({"type": "bullet", "data": bullet}) + "\n"
        client_player.sendall(msg.encode())
    except Exception as error:
        print("Error sending bullet:", error)

class HealthBar():
    def __init__(self, w, h, max_hp):
        self.w = w
        self.h = h
        self.hp = max_hp
        self.max_hp = max_hp

    def draw(self, surface, x, y):
        ratio = max(self.hp / self.max_hp, 0)
        # Background Red.
        pygame.draw.rect(surface, "red", (x, y, self.w, self.h))
        # Forground Green representing full health.
        pygame.draw.rect(surface, "green", (x, y, self.w * ratio, self.h))

player_health = HealthBar(w=45, h=7, max_hp=30)


running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_x, mouse_y = pygame.mouse.get_pos()
            player_fire(mouse_x, mouse_y)

    try:
        client_player.sendall((json.dumps(tank_player) + "\n").encode())
    except Exception as error:
        print("Connection error:", error)
        running = False


    # Game Functions.
    player_movement()
    

    # Changes background color, then displays it.
    screen.fill("tan")
    pygame.mouse.set_cursor(cursor)
    pygame.draw.rect(screen, ("Black"), (0,0,WINDOW_WIDTH, WINDOW_HEIGHT), 10)


    # Draw other players.
    for player in others:
        pygame.draw.rect(screen, (255, 0, 0), 
                         (player["x"], player["y"], TANK_WIDTH, TANK_HEIGHT))
        
        other_health = HealthBar(w=TANK_WIDTH, h=5, max_hp=30)
        other_health.hp = player.get("hp", 30)
        other_health.draw(screen, player["x"], player["y"] +36)

    # Draw current player.
    pygame.draw.rect(screen, (0,225,0), 
                     (tank_player["x"], tank_player["y"], TANK_WIDTH, TANK_HEIGHT))
    
    player_health.draw(screen, tank_player["x"], tank_player["y"] + 35)

    for b in bullets:
        pygame.draw.circle(screen, ("Black"), (int(b["x"]), int(b["y"])), 5)


    cooldown_ratio = min((time.time() - last_shot_time) / shot_cooldown, 1.0)
    bar_width = int(TANK_WIDTH * cooldown_ratio)
    bar_height = 5
    bar_x = tank_player["x"]
    bar_y = tank_player["y"] + 40

    pygame.draw.rect(screen, ("Gray"), (bar_x, bar_y, TANK_WIDTH , bar_height ))
    pygame.draw.rect(screen, ("Dark Green"), (bar_x, bar_y, bar_width, bar_height))




    pygame.display.flip()

    # Limits to 60fps
    dt = clock.tick(60) / 1000

pygame.quit()
client_player.close()