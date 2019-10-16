from Ship import Ship, Barrier
import asyncio
import json
from pathlib import Path
import pygame
import time
import sys

RESOURCE_SERVER_IP = '127.0.0.1'
RESOURCE_SERVER_PORT = '8889'
LOOKUPSERVER_IP = '127.0.0.1'
LOOKUPSERVER_PORT = '8888'


class ResourceProtocol(asyncio.Protocol):
    def __init__(self, filename, on_con_lost):
        self.on_con_lost = on_con_lost
        self.filename = filename
        self.file = None

    def connection_made(self, transport):
        messageData = {'filename': self.filename}
        message = json.dumps(messageData)
        transport.write(message.encode())
        print('Data sent: {!r}'.format(message))

    def data_received(self, data):
        if self.file is None:
            self.file = open(self.filename, "wb")
        self.file.write(data)

    def connection_lost(self, exc):
        print('The server closed the connection')
        self.file.close()
        self.on_con_lost.set_result(True)


class LookupProtocol(asyncio.Protocol):
    def __init__(self, messageData, gotServerList):
        self.messageData = messageData
        self.serverList = []
        self.gotServerList = gotServerList

    def connection_made(self, transport):
        self.transport = transport
        self.transport.write(json.dumps(self.messageData).encode())

    def data_received(self, data):
        message = data.decode()
        self.serverList = json.loads(message)
        print(self.serverList)
        self.transport.close()
        if len(self.serverList) == 0:
            self.gotServerList.set_result(False)
        else:
            self.gotServerList.set_result(True)

    def connection_lost(self, exc):
        print('Lookup server connection closed')


class GameClientProtocol:
    def __init__(self, message, on_con_lost, on_con_made, gameData):
        self.message = message
        self.on_con_lost = on_con_lost
        self.on_con_made = on_con_made
        self.gameData = gameData
        self.transport = None
        self.ships = {}

    def connection_made(self, transport):
        self.transport = transport
        self.transport.sendto(self.message.encode())

    def datagram_received(self, data, addr):
        items = json.loads(data.decode())
        ships = items['ships']
        self.gameData['ships'] = ships
        self.gameData['inputs'] = items['inputs']
        self.ships = deserializeGameData(self.gameData)
        if items['handshake'] == 1:
            self.gameData['clientId'] = items['clientId']
            self.on_con_made.set_result(True)

    def error_received(self, exc):
        print('Error received:', exc)

    def connection_lost(self, exc):
        print("Connection closed")
        self.on_con_lost.set_result(True)


def getValidatedShip(oldShipSet, serverShip, ship, imageName):
    if len(oldShipSet) == 0:
        ship = serverShip
    else:
        serverShipStr = json.dumps(
            {"x": serverShip.rect.x, "y": serverShip.rect.y})
        ship.hitpoints = serverShip.hitpoints
        if serverShipStr not in oldShipSet:
            print("Using serverShip")
            ship = serverShip
    if not ship.dead:
        ship.setImage(imageName)
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
    for value in ships.values():
        value.colliding = False
    for key, value in ships.items():
        if len(gameData['inputs'][key]) > 0:
            itemInputs = gameData['inputs'][key].pop(0)
            shipList = list(ships.values())
            shipList.remove(value)
            value.handleMovementInput(
                itemInputs['pressed'], deltaTime, shipList)


def handleBullets(ships):
    rectDict = {}
    for key, value in ships.items():
        rectDict[key] = value.rect
    for value in ships.values():
        for bullet in value.gun.bullets:
            oldX = bullet.rect.x
            oldY = bullet.rect.y
            bullet.update()
            interpolation = bullet.interpolate(oldX, oldY)
            for key, rect in rectDict.items():
                collision = rect.collidelist(interpolation)
                if collision != -1:
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


def userSelectServer(serverList):
    if len(serverList) == 0:
        return False
    while True:
        try:
            i = 1
            for server in serverList:
                print("{}: {}".format(i, server['serverName']))
                i = i + 1
            selection = input("Select a server by giving a number: ")
            selValue = int(selection) - 1
            if 0 <= selValue and selValue < len(serverList):
                selectedServer = serverList[selValue]
                return selectedServer
        except IndexError:
            pass
        except ValueError:
            pass


def userSelectColor():
    colors = ['red', 'green', 'blue', 'yellow']
    while True:
        try:
            i = 1
            for color in colors:
                print("{}: {}".format(i, color))
                i = i + 1
            selection = input("Select a server by giving a number: ")
            selValue = int(selection) - 1
            if 0 <= selValue and selValue < len(colors):
                selectedColor = colors[selValue]
                return selectedColor
        except IndexError:
            pass
        except ValueError:
            pass


async def fetchResource(loop, filename):
    on_con_lost = loop.create_future()
    transport, protocol = await loop.create_connection(
        lambda: ResourceProtocol(filename, on_con_lost),
        RESOURCE_SERVER_IP, RESOURCE_SERVER_PORT)
    await on_con_lost


async def main():
    # Get a reference to the event loop as we plan to use
    # low-level APIs.
    loop = asyncio.get_running_loop()

    on_con_lost = loop.create_future()
    on_con_made = loop.create_future()
    message = '{"handshake": 1}'
    gameData = {}
    lookupMessageData = {'type': 'query'}
    gotServerList = loop.create_future()
    lookupTransport, lookUpProtocol = await loop.create_connection(
        lambda: LookupProtocol(
            lookupMessageData, gotServerList),
        LOOKUPSERVER_IP, LOOKUPSERVER_PORT
    )
    await gotServerList
    color = userSelectColor()
    shipImageName = color + '.png'
    shipImage = Path(shipImageName)
    if not shipImage.is_file():
        await fetchResource(loop, shipImageName)
    server = userSelectServer(lookUpProtocol.serverList)
    if not server:
        print("No servers were online :(")
        sys.exit(0)

    transport, protocol = await loop.create_datagram_endpoint(
        lambda: GameClientProtocol(
            message, on_con_lost, on_con_made, gameData),
        remote_addr=(server['ip'], server['port']))

    try:
        await on_con_made
        pygame.init()
        screen = pygame.display.set_mode((1900, 900))
        barriers = [
            Barrier((0, 0), (1900, 40)),
            Barrier((0, 860), (1900, 40)),
            Barrier((0, 0), (40, 900)),
            Barrier((1860, 0), (40, 900)),
        ]
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
        ship = None
        while True:
            ships = protocol.ships
            serverShip = ships[str(clientId)]
            ship = getValidatedShip(
                oldShipSet, serverShip, ship, shipImageName)
            ships[str(clientId)] = ship
            deltaTime, newTime = getDeltaTime(oldTime)
            oldTime = newTime
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    quit()
            pressed = pygame.key.get_pressed()
            inputStruct = {"pressed": pressed,
                           "delta": deltaTime, "timestamp": newTime}
            gameData['inputs'][str(clientId)] = [inputStruct]
            inputBuffer.append(inputStruct)
            handleShipMovements(ships, gameData, deltaTime)
            handleBullets(ships)
            handleBarriers(ships, barriers)
            # Drawing
            screen.fill(BLACK)
            for barrier in barriers:
                screen.blit(barrier.image, barrier.rect)
            for value in ships.values():
                image = pygame.transform.rotate(
                    value.image, value.getDirection())
                screen.blit(image, value.rect)
                screen.blit(value.hpbar.image, value.hpbar.rect)
                for bullet in value.gun.bullets:
                    transformedBullet = pygame.transform.rotate(
                        bullet.image, bullet.direction)
                    screen.blit(transformedBullet, bullet.rect)
            pygame.display.update()  # Or 'pygame.display.flip()'.
            # Drawing end
            elapsed = newTime - lastSentTime
            oldShipSet.append(json.dumps(
                {"x": ship.rect.x, "y": ship.rect.y}))
            if elapsed >= 0.05:
                message = createMessage(inputBuffer, clientId, newTime)
                transport.sendto(message.encode())
                lastSentTime = newTime
                inputBuffer = []
                if len(oldShipSet) > 15:
                    oldShipSet = oldShipSet[-30:]
            if ship.dead:
                oldShipSet = []
            await asyncio.sleep(0.0)
            clock.tick(FPS)
        await on_con_lost
    finally:
        transport.close()


asyncio.run(main())
