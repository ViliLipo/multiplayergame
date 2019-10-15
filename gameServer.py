from Ship import Ship, Barrier
import asyncio
import json
import pygame
import random
import time


class LookupProtocol(asyncio.Protocol):
    def __init__(self, messageData, on_con_lost):
        self.messageData = messageData
        self.on_con_lost = on_con_lost

    def connection_made(self, transport):
        print(self.messageData)
        transport.write(json.dumps(self.messageData).encode())

    def data_received(self, data):
        message = data.decode()
        information = json.loads(message)
        print(information)

    def connection_lost(self, exc):
        self.on_con_lost.set_result(True)
        print('Lookup server connection closed')


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
            x = random.randint(0, 720)
            y = random.randint(0, 480)
            ship = Ship(x, y)
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


def handleBullets(ships):
    rectDict = {}
    for key, value in ships.items():
        rectDict[key] = value.rect
    for value in ships.values():
        for bullet in value.gun.bullets:
            bullet.update()
            for key, rect in rectDict.items():
                if bullet.rect.colliderect(rect):
                    ship = ships[key]
                    ship.takeDamage(1)
                    bullet.age = 1000
        value.gun.expireOldBullets()


def handleBarriers(ships, barriers):
    for barrier in barriers:
        for ship in ships.values():
            if barrier.rect.colliderect(ship.rect):
                ship.takeDamage(2)
                ship.direction = ship.direction + 180


def handleRespawns(ships):
    for value in ships.values():
        value.spawn()


async def main():
    print("Starting UDP server")
    loop = asyncio.get_running_loop()
    gameData = {}
    clients = {}
    serverName = 'SpaceShooter Server #1'
    ip = '127.0.0.1'
    port = 9999
    lookupMessageData = {
        'type': 'declaration',
        'serverName': serverName,
        'ip': ip,
        'port': port
    }
    on_con_lost = loop.create_future()
    lookupTransport, lookUpProtocol = await loop.create_connection(
        lambda: LookupProtocol(
            lookupMessageData, on_con_lost), '127.0.0.1', 8888
    )
    await on_con_lost
    lookupTransport.close()
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
        barriers = [
            Barrier((0, 0), (1900, 40)),
            Barrier((0, 860), (1900, 40)),
            Barrier((0, 0), (40, 900)),
            Barrier((1860, 0), (40, 900)),
        ]
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
            for value in gameData.values():
                value.colliding = False
            for key, value in gameData.items():
                screen.blit(value.image, value.rect)
                screen.blit(value.hpbar.image, value.hpbar.rect)
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
                for bullet in value.gun.bullets:
                    transformedBullet = pygame.transform.rotate(
                        bullet.image, bullet.direction)
                    screen.blit(transformedBullet, bullet.rect)
            handleBullets(newGameData)
            handleBarriers(newGameData, barriers)
            handleRespawns(newGameData)
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
