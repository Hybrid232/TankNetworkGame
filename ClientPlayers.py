import socket
import threading 
import pygame 
import json
import time
import random
import math

HOST = "127.0.0.1"
# BYU-I Lan Server: 10.244.53.130
# HOST = input("Enter the server IP to connect (LAN IP of host): ").strip()
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
#------------------------------------------------------------------------------

# Initialize Pygame.
pygame.init()

# Window Information.
BORDER_THICKNESS = 10
WINDOW_WIDTH = 700
WINDOW_HEIGHT = 700

# Tank Size.
TANK_WIDTH = 50
TANK_HEIGHT = 50

# Gameplay Displays.
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("Tanks Alot")
clock = pygame.time.Clock()
dt = 0
cursor = pygame.cursors.Cursor(pygame.SYSTEM_CURSOR_CROSSHAIR) 

# Images.
green_tank = pygame.image.load("Images/green_tank.png")
green_tank = pygame.transform.scale(green_tank, (TANK_WIDTH, TANK_HEIGHT))
explosion_img = pygame.image.load("Images/tank_explosion.jpg").convert_alpha()
EXPLOSION_SIZE = (50, 50)
explosion_img = pygame.transform.scale(explosion_img, EXPLOSION_SIZE)
EXPLOSION_DURATION = 0.5

# Lists and dictionaries.
tank_player = {"x": 250, "y": 200}
others = []
bullets = []
explosions = []
walls = [
    {"x": 200, "y": 150, "w": 100, "h": 20},
    {"x": 400, "y": 300, "w": 20, "h": 100}
]

# Shooting Cool down Variables.
last_shot_time = 0
shot_cool_down = 1
last_respawn_time = 0

#------------------------------------------------------------------------------
buffer = ""
# Receives the information from the server to display for the Clients.
def receive_thread():
    global others, bullets, buffer, walls
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
                    others = [p for p in msg.get("players", [])
                              if p.get("id") != my_id]
                   
                    for p in msg.get("players", []):
                        if p.get("id") == my_id:
                            tank_player["x"] = lerp(tank_player["x"], 
                                                              p["x"], 0.2) 
                            tank_player["y"] = lerp(tank_player["y"], 
                                                              p["y"], 0.2)
                            player_health.hp = p.get("hp", 30)

                        else:
                            found = False
                            for o in others:
                                if o["id"] == p["id"]:
                                    o["x"], o["y"], o["hp"] = \
                                    p["x"], p["y"], p["hp"]
                                    found = True
                                    break
                                if not found:
                                    others.append(p) 
                    
                    bullets = msg.get("bullets", [])
                    walls = msg.get("walls", [])
                    explosions = msg.get("explosions", [])

                except json.JSONDecodeError as error:
                    print(f"JSON error in receive_thread function: \
                           {error}, line={line}")

        except socket.timeout:
            continue
        except Exception as error:
            print(f"Receive thread connection error: {error}")
            break

threading.Thread(target=receive_thread, daemon=True).start()

def lerp(a, b, t):
    return a + (b - a) * t

# Player Movement.-------------------------------------------------------------
def player_movement():
    dx = 0
    dy = 0
    player_speed = 150

    keys = pygame.key.get_pressed()
    if keys[pygame.K_w]:
        dy = -player_speed * dt
    if keys[pygame.K_s]:
        dy = player_speed * dt
    if keys[pygame.K_d]:
        dx = player_speed * dt
    if keys[pygame.K_a]:
        dx = -player_speed * dt

    # Keeps player inside the border.
    tank_player["x"] = max(BORDER_THICKNESS, min(tank_player["x"],
                           WINDOW_WIDTH - BORDER_THICKNESS - TANK_WIDTH))
    tank_player["y"] = max(BORDER_THICKNESS, min(tank_player["y"], 
                           WINDOW_HEIGHT - BORDER_THICKNESS - TANK_HEIGHT))

    # Check for collision for X movement.
    if not check_collision(tank_player["x"] + dx, tank_player["y"]):
        tank_player["x"] += dx

    # Check collision for Y movement.
    if not check_collision(tank_player["x"], tank_player["y"] + dy):
        tank_player["y"] += dy


# Player fire function.--------------------------------------------------------
def player_fire(mouse_x, mouse_y):
    global last_shot_time
    current_time = time.time()

    # Gives cool down so player can't spam shots.
    if current_time - last_shot_time < shot_cool_down:
        return
    last_shot_time = current_time

    # Bullet dictionary.
    bullet = {
        "x": tank_player["x"] + TANK_WIDTH // 2,
        "y": tank_player["y"] + TANK_HEIGHT // 2,
        "vx": 0,
        "vy": 0,
        "owner_id": my_id,
        "ricocheted": False,
        "bounces": 4,

    }

    #
    dx = mouse_x - (tank_player["x"] + TANK_WIDTH // 2)
    dy = mouse_y - (tank_player["y"] + TANK_HEIGHT // 2)
   


    distance = (dx**2 + dy**2)**0.5
    if distance == 0:
        return
    
    # Bullet Speed.
    speed = 500

    bullet["vx"] = dx / distance * speed
    bullet["vy"] = dy / distance * speed

    # Server info to send to all clients.
    try:
        msg = json.dumps({"type": "bullet", "data": bullet}) + "\n"
        client_player.sendall(msg.encode())
    except Exception as error:
        print("Error sending bullet:", error)

# Health bar Class-------------------------------------------------------------
class HealthBar():
    def __init__(self, w, h, max_hp):
        self.w = w
        self.h = h
        self.hp = max_hp
        self.max_hp = max_hp

    # Draws the Health Bar
    def draw(self, surface, x, y):
        ratio = max(self.hp / self.max_hp, 0)
        # Background Red showing player is dead.
        pygame.draw.rect(surface, "red", (x, y, self.w, self.h))
        # Foreground Green representing full health.
        pygame.draw.rect(surface, "green", (x, y, self.w * ratio, self.h))

# Health variable to signify the health bar's width, height, and total HP.
player_health = HealthBar(w=45, h=7, max_hp=30)

#------------------------------------------------------------------------------
# Wall Collision
def check_collision(x, y):
    tank_rect = pygame.Rect(x, y, TANK_WIDTH, TANK_HEIGHT)
    
    for wall in walls:
        wall_rect= pygame.Rect(wall["x"], wall["y"], wall["w"], wall["h"])
        if tank_rect.colliderect(wall_rect):
            return True
        
    for player in others:
        player_rect = pygame.Rect(player["x"], player["y"],
                                  TANK_WIDTH, TANK_HEIGHT)
        if tank_rect.colliderect(player_rect):
            return True
    return False
#------------------------------------------------------------------------------

# Gameplay loop.
running = True
while running:
    # Allows player to press the exit button and close the application.
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        # If user clicks with their mouse, it causes them to shoot from the 
        # tank to where the mouse was pressed.
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_x, mouse_y = pygame.mouse.get_pos()
            player_fire(mouse_x, mouse_y)

    # Tests to make sure the client is connected. Closes the application if
    # it couldn't connect.
    if time.time() - last_respawn_time > 0.5:
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

    for wall in walls:
        pygame.draw.rect(screen, (100, 100, 100), (wall["x"], wall["y"],
                                               wall["w"], wall["h"]))

    # Draw other players.
    for player in others:
        pygame.draw.rect(screen, (255, 0, 0), 
                         (player["x"], player["y"], TANK_WIDTH, TANK_HEIGHT))
        
        # Draw Health Bar for other players.
        other_health = HealthBar(w=TANK_WIDTH, h=5, max_hp=30)
        other_health.hp = player.get("hp", 30)
        other_health.draw(screen, player["x"], player["y"] + TANK_HEIGHT - 50)

    # Draw current player.
    mouse_x, mouse_y = pygame.mouse.get_pos()
    dx = mouse_x - (tank_player["x"] + TANK_WIDTH//2)
    dy = mouse_y - (tank_player["y"] + TANK_HEIGHT//2)
    angle = -math.degrees(math.atan2(dy,dx))
    rotated_tank = pygame.transform.rotate(green_tank, angle)

    rect = rotated_tank.get_rect(center=(tank_player["x"] + TANK_WIDTH//2, tank_player["y"] + TANK_HEIGHT//2))
    screen.blit(rotated_tank, rect.topleft)
    
    # Draws the Health Bar for the current player.
    player_health.draw(screen, tank_player["x"],
                        tank_player["y"] + TANK_WIDTH - 75)

    # Draw Bullets
    for b in bullets:
        pygame.draw.circle(screen, ("Black"), (int(b["x"]), int(b["y"])), 5)
        
    # Shows recharge bar below the player.
    cool_down_ratio = min((time.time() - last_shot_time) / shot_cool_down, 1.0)
    bar_width = int(TANK_WIDTH * cool_down_ratio)
    bar_height = 5
    bar_x = tank_player["x"]
    bar_y = tank_player["y"] - 15

    pygame.draw.rect(screen, ("Gray"), 
                    (bar_x, bar_y, TANK_WIDTH , bar_height ))
    pygame.draw.rect(screen, ("Dark Green"), 
                    (bar_x, bar_y, bar_width, bar_height))

    # Draws Explosion
    current_time = time.time()
    for exp in explosions[:]:
        if current_time - exp["time"] > EXPLOSION_DURATION:
            explosions.remove(exp)
        else:
            screen.blit(explosion_img, (exp["x"], exp["y"]))

    pygame.display.flip()

    # Limits to 60fps
    dt = clock.tick(60) / 1000

pygame.quit()
client_player.close()