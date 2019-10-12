import asyncio
import pygame
import json
import time
import math


class Bullet(pygame.sprite.Sprite):
    def __init__(self, direction, x, y):
        super().__init__()
        self.image = pygame.Surface((10, 10))
        self.image.fill((255, 255, 255))
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y
        self.direction = direction
        if self.direction == 0:
            self.direction = 360
        self.age = 0

    def update(self):
        speed = 100
        xSpeed = -math.sin(math.radians(self.direction)) * speed
        ySpeed = -math.cos(math.radians(self.direction)) * speed
        self.rect.move_ip(xSpeed, ySpeed)


class Ship(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.image = pygame.image.load('ship.png')
        self.rect = self.image.get_rect()
        self.velocity = [0, 0]
        self.direction = 0

    def update(self, ships):
        self.handleInterShipCollision(ships)
        self.rect.move_ip(
            round(self.velocity[0], 0), round(self.velocity[1], 0))

    def handleInterShipCollision(self, ships):
        collision = False
        for ship in ships:
            if self.rect.colliderect(ship.rect):
                collision = True
        if collision:
            self.velocity[0] = self.velocity[0] * -20
            self.velocity[1] = self.velocity[1] * -20
        return collision

    def handleMovementInput(self, pressed, deltaTime, ships):
        self.velocity = [0, 0]
        if pressed[pygame.K_w]:
            self.velocity[1] = -100 * deltaTime
        elif pressed[pygame.K_s]:
            self.velocity[1] = 100 * deltaTime
        if pressed[pygame.K_a]:
            self.velocity[0] = -100 * deltaTime
        elif pressed[pygame.K_d]:
            self.velocity[0] = 100 * deltaTime
        self.update(ships)

    def isSame(self, ship):
        return self.rect.x == ship.rect.x and self.rect.y == ship.rect.y

    def jsonSerialize(self):
        data = {"x": self.rect.x,
                "y": self.rect.y,
                "h": self.rect.h,
                "w": self.rect.w,
                "velocity": self.velocity
                }
        return data

    def jsonDeserialize(ship):
        newShip = Ship()
        x = ship["x"]
        y = ship["y"]
        velocity = ship["velocity"]
        newShip.rect.x = x
        newShip.rect.y = y
        newShip.velocity = velocity
        return newShip

    def getDirection(self):
        angle = 0
        if self.velocity[0] > 0 and self.velocity[1] == 0:
            return 270
        elif self.velocity[0] < 0 and self.velocity[1] == 0:
            return 90
        elif self.velocity[0] == 0 and self.velocity[1] > 0:
            return 180
        elif self.velocity[0] == 0 and self.velocity[1] < 0:
            return 0
        elif self.velocity[0] == 0 and self.velocity[1] == 0:
            return 0
        elif self.velocity[1] > 0 and self.velocity[0] > 0:
            angle = 225
        elif self.velocity[1] > 0 and self.velocity[0] < 0:
            angle = 135
        elif self.velocity[1] < 0 and self.velocity[0] > 0:
            angle = 315
        elif self.velocity[1] < 0 and self.velocity[0] < 0:
            angle = 45
        return angle


class GameClientProtocol:
    def __init__(self, message, on_con_lost, on_con_made, gameData):
        self.message = message
        self.on_con_lost = on_con_lost
        self.on_con_made = on_con_made
        self.gameData = gameData
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        self.transport.sendto(self.message.encode())

    def datagram_received(self, data, addr):
        items = json.loads(data.decode())
        ships = items['ships']
        self.gameData['ships'] = ships
        self.gameData['inputs'] = items['inputs']
        if items['handshake'] == 1:
            self.gameData['clientId'] = items['clientId']
            self.on_con_made.set_result(True)

    def error_received(self, exc):
        print('Error received:', exc)

    def connection_lost(self, exc):
        print("Connection closed")
        self.on_con_lost.set_result(True)


def getValidatedShip(oldShipSet, serverShip, ship):
    if len(oldShipSet) == 0:
        ship = serverShip
    else:
        serverShipStr = json.dumps(
            {"x": serverShip.rect.x, "y": serverShip.rect.y})
        if serverShipStr not in oldShipSet:
            print("Using serverShip")
            ship = serverShip
    return ship


def getDeltaTime(oldTime):
    newTime = time.time()
    deltaTime = round(newTime - oldTime, 4)
    return deltaTime, newTime


def deserializeGameData(gameData):
    ships = {}
    for key, value in gameData['ships'].items():
        ships[key] = Ship.jsonDeserialize(value)
    return ships


def createMessage(inputBuffer, clientId, time):
    messageData = {"handshake": 0}
    messageData['inputs'] = inputBuffer
    messageData['clientId'] = clientId
    messageData['timeStamp'] = time
    message = json.dumps(messageData)
    return message


def handleShipMovements(ships, gameData, deltaTime):
    for key, value in ships.items():
        if len(gameData['inputs'][key]) > 0:
            itemInputs = gameData['inputs'][key].pop(0)
            shipList = list(ships.values())
            shipList.remove(value)
            value.handleMovementInput(
                itemInputs['pressed'], deltaTime, shipList)


async def main():
    # Get a reference to the event loop as we plan to use
    # low-level APIs.
    loop = asyncio.get_running_loop()

    on_con_lost = loop.create_future()
    on_con_made = loop.create_future()
    message = '{"handshake": 1}'
    gameData = {}
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: GameClientProtocol(
            message, on_con_lost, on_con_made, gameData),
        remote_addr=('127.0.0.1', 9999))

    try:
        await on_con_made
        pygame.init()
        screen = pygame.display.set_mode((720, 480))
        pygame.display.set_caption("SpaceShooter client")
        clock = pygame.time.Clock()
        FPS = 60
        BLACK = (0, 0, 0)
        WHITE = (255, 255, 255)
        clientId = gameData['clientId']
        image = pygame.Surface((32, 32))
        image.fill(WHITE)
        oldTime = time.time()
        lastSentTime = time.time()
        oldShipSet = []
        inputBuffer = []
        i = 0
        ship = None
        while True:
            ships = deserializeGameData(gameData)
            serverShip = ships[str(clientId)]
            ship = getValidatedShip(oldShipSet, serverShip, ship)
            ships[str(clientId)] = ship
            deltaTime, newTime = getDeltaTime(oldTime)
            oldTime = newTime
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    quit()
            pressed = pygame.key.get_pressed()
            inputStruct = {"pressed": pressed, "delta": deltaTime}
            gameData['inputs'][str(clientId)] = [inputStruct]
            inputBuffer.append(inputStruct)
            handleShipMovements(ships, gameData, deltaTime)
            # Drawing
            screen.fill(BLACK)
            for value in ships.values():
                image = pygame.transform.rotate(
                    value.image, value.getDirection())
                screen.blit(image, value.rect)
            pygame.display.update()  # Or 'pygame.display.flip()'.
            # Drawing end
            elapsed = newTime - lastSentTime
            i = i + 1
            if elapsed >= 0.05:
                oldShipSet.append(json.dumps(
                    {"x": ship.rect.x, "y": ship.rect.y}))
                message = createMessage(inputBuffer, clientId, newTime)
                transport.sendto(message.encode())
                lastSentTime = newTime
                inputBuffer = []
                if len(oldShipSet) > 5:
                    oldShipSet = oldShipSet[-30:]
            await asyncio.sleep(0.0)  # Serve for 1 hour.
            clock.tick(FPS)
        await on_con_lost
    finally:
        transport.close()


asyncio.run(main())
