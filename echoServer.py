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

    def update(self):
        self.rect.move_ip((self.velocity[0], self.velocity[1]))

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


class EchoServerProtocol:
    def __init__(self, item, clients):
        self.item = item
        self.clients = clients
        self.timeStamps = {}

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        message = data.decode()
        information = json.loads(message)
        if information['handshake'] == 1:
            clientId = random.randint(0, 2000)
            ship = Ship()
            ship.x = 0
            ship.y = 0
            replyData = {
                'handshake': 1,
                'clientId': clientId,
                'ships': {
                    clientId: ship.jsonSerialize()
                }
            }
            self.transport.sendto(json.dumps(replyData).encode(), addr)
            self.clients[clientId] = addr
            self.item[clientId] = Ship.jsonDeserialize({"x": 0, "y": 0})
            self.timeStamps[clientId] = time.time()
        else:
            client = information['clientId']
            pressed = information['pressed']
            ship = self.item[client]
            oldTime = self.timeStamps[client]
            newTime = information['timeStamp']
            elapsed = newTime - oldTime
            ship.velocity = [0, 0]
            if pressed[pygame.K_w]:
                ship.velocity[1] = -100 * elapsed
            elif pressed[pygame.K_s]:
                ship.velocity[1] = 100 * elapsed
            if pressed[pygame.K_a]:
                ship.velocity[0] = -100 * elapsed
            elif pressed[pygame.K_d]:
                ship.velocity[0] = 100 * elapsed
            ship.update()
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
        lambda: EchoServerProtocol(gameData, clients),
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
            messageData["ships"] = {}
            messageData["handshake"] = 0
            messageData["timeStamp"] = time.time()
            for key, value in gameData.items():
                # value.update()
                screen.blit(value.image, value.rect)
                messageData["ships"][key] = value.jsonSerialize()
            for key, value in clients.items():
                messageData["clientId"] = key
                message = json.dumps(messageData)
                transport.sendto(message.encode(), value)
            pygame.display.update()
            await asyncio.sleep(0.01)
    finally:
        transport.close()
        quit()


asyncio.run(main())
