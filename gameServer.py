import asyncio
import pygame
import json
import time
import random


class Ship(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.image = pygame.Surface((32, 32))
        self.image.fill((255, 255, 255))
        self.rect = self.image.get_rect()
        self.velocity = [0, 0]

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
        newShip.rect.x = x
        newShip.rect.y = y
        return newShip

    def deepCopy(self):
        newShip = Ship()
        newShip.rect.x = self.rect.x
        newShip.rect.y = self.rect.y
        newShip.velocity = self.velocity
        return newShip


class GameServerProtocol:
    def __init__(self, item, clients):
        self.item = item
        self.clients = clients
        self.timeStamps = {}
        self.inputBuffer = {}

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        message = data.decode()
        information = json.loads(message)
        if information['handshake'] == 1:
            clientId = random.randint(0, 2000)
            ship = Ship()
            ship.rect.x = random.randint(0, 720)
            ship.rect.y = random.randint(0, 480)
            replyData = {
                'handshake': 1,
                'clientId': clientId,
                'ships': {
                    clientId: ship.jsonSerialize()
                },
                'inputs': {},
            }
            self.transport.sendto(json.dumps(replyData).encode(), addr)
            self.clients[clientId] = addr
            self.item[clientId] = ship
            self.timeStamps[clientId] = time.time()
            self.inputBuffer[clientId] = []
        else:
            client = information['clientId']
            inputs = information['inputs']
            ship = self.item[client]
            newTime = information['timeStamp']
            self.inputBuffer[client] = self.inputBuffer[client] + inputs
            self.timeStamps[client] = newTime


async def main():
    print("Starting UDP server")

    # Get a reference to the event loop as we plan to use
    # low-level APIs.
    loop = asyncio.get_running_loop()

    # One protocol instance will be created to serve all
    # client requests.
    gameData = {}
    clients = {}
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: GameServerProtocol(gameData, clients),
        local_addr=('127.0.0.1', 9999))

    try:
        pygame.init()
        pygame.display.set_caption("SpaceShooter server")
        screen = pygame.display.set_mode((720, 480))
        BLACK = (0, 0, 0)
        WHITE = (255, 255, 255)
        image = pygame.Surface((32, 32))
        image.fill(WHITE)
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    transport.close()
                    quit()
                    break
            screen.fill(BLACK)
            messageData = {}
            messageData["inputs"] = {}
            messageData["ships"] = {}
            messageData["handshake"] = 0
            messageData["timeStamp"] = time.time()
            newGameData = {}
            for key, value in gameData.items():
                # value.update()
                screen.blit(value.image, value.rect)
                messageData["ships"][key] = value.jsonSerialize()
                messageData["inputs"][key] = protocol.inputBuffer[key]
                shipCopy = gameData[key].deepCopy()
                for i in protocol.inputBuffer[key]:
                    deltaTime = i["delta"]
                    pressed = i["pressed"]
                    ships = list(gameData.values())
                    ships.remove(value)
                    shipCopy.handleMovementInput(pressed, deltaTime, ships)
                newGameData[key] = shipCopy
            for key, value in clients.items():
                messageData["clientId"] = key
                messageData["ships"][key] = newGameData[key].jsonSerialize()
                message = json.dumps(messageData)
                transport.sendto(message.encode(), value)
                protocol.inputBuffer[key] = []
                messageData["ships"][key] = gameData[key].jsonSerialize()
            for key, value in newGameData.items():
                gameData[key] = value
            pygame.display.update()
            await asyncio.sleep(0.05)
    finally:
        transport.close()
        quit()


asyncio.run(main())
