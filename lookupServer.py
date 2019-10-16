#!/bin/python
import asyncio
import json
import time

IP = '127.0.0.1'
PORT = '8888'


def serverEqual(server1, server2):
    return (server1['ip'] == server2['ip']
            and server1['port'] == server2['port'])


def serverInList(server, serverList):
    for s in serverList:
        if serverEqual(server, s):
            return s
    return False


def hearbeatFilter(server):
    now = time.time()
    if now - server['hearbeat'] > 30:
        return False
    else:
        return True


class LookupServerProtocol(asyncio.Protocol):
    def __init__(self, serverList):
        self.serverList = serverList

    def connection_made(self, transport):
        self.transport = transport

    def data_received(self, data):
        message = data.decode()
        information = json.loads(message)
        for server in self.serverList:
            if not hearbeatFilter(server):
                self.serverList.remove(server)
        if information['type'] == 'declaration':
            if not serverInList(information, self.serverList):
                information['hearbeat'] = time.time()
                self.serverList.append(information)
            else:
                server = serverInList(information, self.serverList)
                server['heartbeat'] = time.time()
            replyData = {'code': 'ok'}
            self.transport.write(json.dumps(replyData).encode())
        elif information['type'] == 'query':
            reply = json.dumps(self.serverList)
            self.transport.write(reply.encode())
        self.transport.close()


async def main():
    loop = asyncio.get_running_loop()
    serverList = []
    server = await loop.create_server(
        lambda: LookupServerProtocol(serverList),
        IP, PORT)
    async with server:
        await server.serve_forever()
    pass


if __name__ == '__main__':
    asyncio.run(main())
