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

    def update(self):
        self.rect.move_ip(
            round(self.velocity[0], 0), round(self.velocity[1], 0))

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

    def handleMovementInput(self, pressed, deltaTime):
        self.velocity = [0,0]
        if pressed[pygame.K_w]:
            self.velocity[1] = -100 * deltaTime
        elif pressed[pygame.K_s]:
            self.velocity[1] = 100 * deltaTime
        if pressed[pygame.K_a]:
            self.velocity[0] = -100 * deltaTime
        elif pressed[pygame.K_d]:
            self.velocity[0] = 100 * deltaTime
        self.update()



class EchoClientProtocol:
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


async def main():
    # Get a reference to the event loop as we plan to use
    # low-level APIs.
    loop = asyncio.get_running_loop()

    on_con_lost = loop.create_future()
    on_con_made = loop.create_future()
    message = '{"handshake": 1}'
    gameData = {}
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: EchoClientProtocol(
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
        print(clientId)
        image = pygame.Surface((32, 32))
        image.fill(WHITE)
        oldTime = time.time()
        lastSentTime = time.time()
        bullets = []
        oldShipSet = []
        inputBuffer = []
        i = 0
        while True:
            clientShipData = gameData['ships'][str(clientId)]
            if len(oldShipSet) == 0:
                ship = Ship.jsonDeserialize(clientShipData)
            else:
                serverShip = Ship.jsonDeserialize(clientShipData)
                serverShipStr = json.dumps(
                    {"x": serverShip.rect.x, "y": serverShip.rect.y})
                if serverShipStr not in oldShipSet:
                    print("Using serverShip")
                    ship = serverShip
            newTime = time.time()
            deltaTime = round(newTime - oldTime, 4)
            oldTime = newTime
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    quit()
            pressed = pygame.key.get_pressed()
            ship.velocity = [0, 0]
            if pressed[pygame.K_w]:
                ship.velocity[1] = -100 * deltaTime
            elif pressed[pygame.K_s]:
                ship.velocity[1] = 100 * deltaTime
            if pressed[pygame.K_a]:
                ship.velocity[0] = -100 * deltaTime
            elif pressed[pygame.K_d]:
                ship.velocity[0] = 100 * deltaTime
            if pressed[pygame.K_SPACE]:
                bullet = Bullet(ship.getDirection(),
                                ship.rect.x, ship.rect.y)
                bullets.append(bullet)
            ship.update()
            rotatedImage = pygame.transform.rotate(
                ship.image, ship.getDirection())
            screen.fill(BLACK)
            screen.blit(rotatedImage, ship.rect)
            for key, value in gameData['ships'].items():
                if key != str(clientId):
                    gameItem = Ship.jsonDeserialize(value)
                    if len(gameData['inputs'][key]) > 0:
                        print(len(gameData['inputs'][key]))
                        itemInputs = gameData['inputs'][key].pop(0)
                        gameItem.handleMovementInput(itemInputs['pressed'], deltaTime)
                    image = pygame.transform.rotate(
                        gameItem.image, gameItem.getDirection())
                    screen.blit(image, gameItem.rect)
            for bullet in bullets:
                bullet.update()
                screen.blit(bullet.image, bullet.rect)
            pygame.display.update()  # Or 'pygame.display.flip()'.
            inputBuffer.append({"pressed": pressed, "delta": deltaTime})
            messageData = {"handshake": 0}
            messageData['inputs'] = inputBuffer
            messageData['clientId'] = gameData['clientId']
            messageData['timeStamp'] = newTime
            elapsed = newTime - lastSentTime
            i = i + 1
            if elapsed >= 0.05:
                oldShipSet.append(json.dumps(
                    {"x": ship.rect.x, "y": ship.rect.y}))
                message = json.dumps(messageData)
                transport.sendto(message.encode())
                lastSentTime = newTime
                inputBuffer = []
                if len(oldShipSet) > 15:
                    oldShipSet = oldShipSet[-30:]
            await asyncio.sleep(0.011)  # Serve for 1 hour.
            clock.tick(FPS)
        await on_con_lost
    finally:
        transport.close()


asyncio.run(main())
