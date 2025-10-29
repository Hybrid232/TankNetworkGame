import socket
import threading 
import pygame 
import json
import time
import random

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
#------------------------------------------------------------------------------

# Initialize Pygame.
pygame.init()

# Window Information.
BORDER_THICKNESS = 10
WINDOW_WIDTH = 700
WINDOW_HEIGHT = 700

# Tank Size.
TANK_WIDTH = 45
TANK_HEIGHT = 30

# Gameplay Displays.
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("Multiplayer Tank Game")
clock = pygame.time.Clock()
dt = 0
cursor = pygame.cursors.Cursor(pygame.SYSTEM_CURSOR_CROSSHAIR) 

# Images.
explosion_img = pygame.image.load("Images/tank_explosion.jpg").convert_alpha()
EXPLOSION_SIZE = (50, 50)
explosion_img = pygame.transform.scale(explosion_img, EXPLOSION_SIZE)
EXPLOSION_DURATION = 0.5

# Lists and dictionaries.
tank_player = {"x": 250, "y": 200}
others = []
bullets = []
explosions = []

# Shooting Cool down Variables.
last_shot_time = 0
shot_cool_down = 1

#------------------------------------------------------------------------------
buffer = ""
# Receives the information from the server to display for the Clients.
def receive_thread():
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
                    others = [p for p in msg.get("players", [])
                              if p.get("id") != my_id]
                   
                    for p in msg.get("players", []):
                        if p.get("id") == my_id:
                            player_health.hp = p.get("hp", 30)
                    
                    bullets = msg.get("bullets", [])
                except json.JSONDecodeError as error:
                    print(f"JSON error in receive_thread function: \
                           {error}, line={line}")

        except socket.timeout:
            continue
        except Exception as error:
            print(f"Receive thread connection error: {error}")
            break

threading.Thread(target=receive_thread, daemon=True).start()

# Player Movement.-------------------------------------------------------------
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

    # Keeps player inside the border.
    tank_player["x"] = max(BORDER_THICKNESS, min(tank_player["x"],
                           WINDOW_WIDTH - BORDER_THICKNESS - TANK_WIDTH))
    tank_player["y"] = max(BORDER_THICKNESS, min(tank_player["y"], 
                           WINDOW_HEIGHT - BORDER_THICKNESS - TANK_HEIGHT))

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
        "owner_id": my_id
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
        
        # Draw Health Bar for other players.
        other_health = HealthBar(w=TANK_WIDTH, h=5, max_hp=30)
        other_health.hp = player.get("hp", 30)
        other_health.draw(screen, player["x"], player["y"] + TANK_HEIGHT + 5)

    # Draw current player.
    pygame.draw.rect(screen, (0,225,0), 
                     (tank_player["x"], tank_player["y"],
                     TANK_WIDTH, TANK_HEIGHT))
    
    # Draws the Health Bar for the current player.
    player_health.draw(screen, tank_player["x"],
                        tank_player["y"] + TANK_WIDTH - 65)

    # Draw Bullets
    for b in bullets:
        pygame.draw.circle(screen, ("Black"), (int(b["x"]), int(b["y"])), 5)

    # Shows recharge bar below the player.
    cool_down_ratio = min((time.time() - last_shot_time) / shot_cool_down, 1.0)
    bar_width = int(TANK_WIDTH * cool_down_ratio)
    bar_height = 5
    bar_x = tank_player["x"]
    bar_y = tank_player["y"] - 15

    pygame.draw.rect(screen, ("Gray"), (bar_x, bar_y, TANK_WIDTH , bar_height ))
    pygame.draw.rect(screen, ("Dark Green"), (bar_x, bar_y, bar_width, bar_height))

    # Draws Explosion
    current_time = time.time()
    for exp in explosions[:]:
        if current_time - exp["time"] > EXPLOSION_DURATION:
            explosions.remove(exp)
        else:
            screen.blit(explosion_img, (exp["x"], exp["y"]))

    # Check Health
    if player_health.hp <= 0:
        screen.blit(explosion_img, (tank_player["x"] - 25, 
                                    tank_player["y"] - 25))
        
        pygame.time.delay(1500)
        pygame.display.flip()

        player_health.hp = player_health.max_hp
        tank_player["x"] = random.randint(50, WINDOW_WIDTH - 50)
        tank_player["y"] = random.randint(50, WINDOW_HEIGHT - 50)




        # explosions.append({
        #     "x": tank_player["x"] + TANK_WIDTH//2 - EXPLOSION_SIZE[0]//2,
        #     "y": tank_player["y"] + TANK_HEIGHT//2 - EXPLOSION_SIZE[1]//2,
        #     "time": time.time()
        # })

        # tank_player["x"], tank_player["y"] = 250, 200
        # player_health.hp = player_health.max_hp
    pygame.display.flip()

    # Limits to 60fps
    dt = clock.tick(60) / 1000

pygame.quit()
client_player.close()