import pygame
import math
import time
import random


class Barrier(pygame.sprite.Sprite):
    def __init__(self, beginpoint, size):
        self.image = pygame.Surface(size)
        self.rect = self.image.get_rect()
        self.rect.x, self.rect.y = beginpoint
        self.image.fill((255, 255, 255))


class Bullet(pygame.sprite.Sprite):
    def __init__(self, direction, x, y):
        super().__init__()
        self.image = pygame.image.load('assets/bullet.png')
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y
        self.direction = direction
        if self.direction == 0:
            self.direction = 360
        self.ttl = 3
        self.age = 0
        self.time = time.time()
        self.update()

    def interpolate(self, startX, startY):
        w = self.image.get_width()
        h = self.image.get_height()
        endX = self.rect.x
        endY = self.rect.y
        lengthX = abs(endX - startX)
        lengthY = abs(endY - startY)
        interpolation = []
        iterations = max(lengthX / w, lengthY / h)
        if startX < endX:
            deltaX = lengthX / iterations
        else:
            deltaX = (lengthX / iterations) * -1
        if startY < endY:
            deltaY = lengthY / iterations
        else:
            deltaY = (lengthY / iterations) * -1
        i = 0
        x = startX
        y = startY
        while i <= iterations:
            rect = pygame.Rect(x, y, w, h)
            interpolation.append(rect)
            if (deltaX < 0 and x > endX) or (deltaX > 0 and x < endX):
                x = x + deltaX
            if (deltaY < 0 and y > endY) or (deltaY > 0 and y < endY):
                y = y + deltaY
            i = i + 1
        return interpolation

    def update(self):
        speed = 60
        xSpeed = -math.sin(math.radians(self.direction)) * speed
        ySpeed = -math.cos(math.radians(self.direction)) * speed
        self.rect.move_ip(xSpeed, ySpeed)
        newTime = time.time()
        self.age = self.age + (newTime - self.time)
        self.time = newTime

    def jsonSerialize(self):
        data = {}
        data["time"] = self.time
        data["x"] = self.rect.x
        data["y"] = self.rect.y
        data["direction"] = self.direction
        data["age"] = self.age
        return data

    def jsonDeserialize(data):
        bullet = Bullet(data['direction'], data['x'], data['y'])
        bullet.time = data["time"]
        bullet.age = data["age"]
        return bullet


class Gun():
    def __init__(self):
        self.lastTimeFired = 0
        self.interval = 0.2
        self.bullets = []

    def shoot(self, direction, x, y):
        if time.time() - self.lastTimeFired > self.interval:
            bullet = Bullet(direction, x, y)
            self.bullets.append(bullet)
            self.lastTimeFired = time.time()

    def expireOldBullets(self):
        self.bullets = list(filter(lambda b: b.age < b.ttl, self.bullets))

    def jsonSerialize(self):
        bullets = list(
            map(lambda bullet: bullet.jsonSerialize(), self.bullets))
        data = {'bullets': bullets, 'lastTimeFired': self.lastTimeFired}
        return data

    def jsonDeserialize(data):
        gun = Gun()
        bulletDataList = data['bullets']
        gun.lastTimeFired = data['lastTimeFired']
        gun.bullets = list(
            map(lambda data: Bullet.jsonDeserialize(data), bulletDataList))
        return gun


class HPBar(pygame.sprite.Sprite):
    def __init__(self, hp, x, y):
        super().__init__()
        h = 15
        w = 40
        self.image = pygame.Surface((40, h))
        # self.image = pygame.image.load('bullet.png')
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y
        greenX = (hp / 10) * w
        self.green = pygame.Surface((greenX, h))
        self.green.fill((0, 255, 0))
        redX = ((10-hp)/10) * w
        self.red = pygame.Surface((redX, h))
        self.red.fill((255, 0, 0))
        self.image.blit(self.red, (greenX, 0))
        self.image.blit(self.green, (0, 0))


class Ship(pygame.sprite.Sprite):
    respawnTimer = 5

    def __init__(self, x, y, hitpoints=10, imageName='assets/ship.png'):
        super().__init__()
        self.image = pygame.image.load(imageName)
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y
        self.velocity = 0
        self.direction = 360
        self.colliding = False
        self.hitpoints = hitpoints
        self.dead = False
        self.gun = Gun()
        self.deadStamp = 0
        self.hpbar = HPBar(self.hitpoints, self.rect.x, self.rect.y - 30)

    def setImage(self, imageName):
        self.image = pygame.image.load(imageName)

    def update(self, ships):
        self.handleInterShipCollision(ships)
        self.handleDeath()
        xSpeed = -math.sin(math.radians(self.direction)) * self.velocity
        ySpeed = -math.cos(math.radians(self.direction)) * self.velocity
        self.rect.move_ip(round(xSpeed, 0), round(ySpeed, 0))
        self.hpbar = HPBar(self.hitpoints, self.rect.x, self.rect.y - 30)

    def takeDamage(self, damage):
        if self.hitpoints > 0:
            self.hitpoints = self.hitpoints - damage
            if self.hitpoints < 0:
                self.hitpoints = 0

    def handleDeath(self):
        if self.hitpoints <= 0:
            if self.deadStamp == 0:
                self.deadStamp = time.time()
            self.dead = True
            self.image = pygame.image.load('assets/explosion.png')

    def spawn(self):
        if self.dead and time.time() - self.deadStamp > Ship.respawnTimer:
            self.rect.x = random.randint(0, 400)
            self.rect.y = random.randint(0, 400)
            self.dead = False
            self.deadStamp = 0
            self.velocity = 0
            self.hitpoints = 10
            self.image = pygame.image.load('assets/ship.png')
            self.colliding = False
            self.hpbar = HPBar(self.hitpoints, self.rect.x, self.rect.y - 30)

    def handleInterShipCollision(self, ships):
        collision = False
        for ship in ships:
            if self.rect.colliderect(ship.rect):
                collision = True
                if not self.colliding and not ship.colliding:
                    self.colliding = True
                    ship.colliding = True
                    self.takeDamage(1)
                    ship.takeDamage(1)
                    oldVelocity = self.velocity
                    oldDir = self.direction
                    self.direction = ship.direction
                    self.velocity = ship.velocity
                    ship.direction = oldDir
                    ship.velocity = oldVelocity
                    xSpeed = - \
                        math.sin(math.radians(self.direction)) * self.velocity
                    ySpeed = - \
                        math.cos(math.radians(self.direction)) * self.velocity
                    self.rect.move_ip(round(xSpeed, 0),
                                      round(ySpeed, 0))
                    xSpeed = - \
                        math.sin(math.radians(ship.direction)) * ship.velocity
                    ySpeed = - \
                        math.cos(math.radians(ship.direction)) * ship.velocity
                    ship.rect.move_ip(round(xSpeed, 0), round(ySpeed, 0))
        return collision

    def handleMovementInput(self, pressed, deltaTime, ships):
        maxVelocity = 15
        if self.dead:
            return
        if pressed[pygame.K_w]:
            self.velocity = 5 * deltaTime + self.velocity
            if self.velocity > maxVelocity:
                self.velocity = maxVelocity
        elif pressed[pygame.K_s]:
            self.velocity = self.velocity - 20 * deltaTime
            if self.velocity < 0:
                self.velocity = 0
        if pressed[pygame.K_a]:
            self.direction = self.direction + 180 * deltaTime
        elif pressed[pygame.K_d]:
            self.direction = self.direction - 180 * deltaTime
        if pressed[pygame.K_SPACE]:
            x, y = self.getCenter()
            x = x - math.sin(math.radians(self.direction)) * self.velocity
            y = y - math.cos(math.radians(self.direction)) * self.velocity
            self.gun.shoot(self.getDirection(), x, y)
        self.update(ships)

    def isSame(self, ship):
        return self.rect.x == ship.rect.x and self.rect.y == ship.rect.y

    def jsonSerialize(self):
        data = {"x": self.rect.x,
                "y": self.rect.y,
                "h": self.rect.h,
                "w": self.rect.w,
                "velocity": self.velocity,
                "hitpoints": self.hitpoints,
                "colliding": self.colliding,
                "dead": self.dead,
                "deadStamp": self.deadStamp,
                "gun": self.gun.jsonSerialize(),
                "direction": self.direction
                }
        return data

    def jsonDeserialize(ship):
        x = ship["x"]
        y = ship["y"]
        hitpoints = ship['hitpoints']
        newShip = Ship(x, y, hitpoints=hitpoints)
        velocity = ship['velocity']
        newShip.rect.x = x
        newShip.rect.y = y
        newShip.velocity = velocity
        newShip.colliding = ship['colliding']
        newShip.dead = ship['dead']
        newShip.deadStamp = ship['deadStamp']
        newShip.gun = Gun.jsonDeserialize(ship['gun'])
        newShip.direction = ship['direction']
        newShip.handleDeath()
        return newShip

    def getDirection(self):
        return self.direction

    def deepCopy(self):
        return Ship.jsonDeserialize(self.jsonSerialize())

    def getCenter(self):
        x = self.rect.x + self.rect.width/2
        y = self.rect.y + self.rect.height/2
        return x, y
