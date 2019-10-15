#!/bin/python
import asyncio
import json


class LookupServerProtocol(asyncio.Protocol):
    def __init__(self, serverList):
        self.serverList = serverList

    def connection_made(self, transport):
        self.transport = transport

    def data_received(self, data):
        message = data.decode()
        information = json.loads(message)
        print('received data')
        if information['type'] == 'declaration':
            print(information)
            self.serverList.append(information)
            print(self.serverList)
            replyData = {'code': 'ok'}
            self.transport.write(json.dumps(replyData).encode())
        elif information['type'] == 'query':
            reply = json.dumps(self.serverList)
            print(self.serverList)
            print(reply)
            self.transport.write(reply.encode())
        self.transport.close()


async def main():
    loop = asyncio.get_running_loop()
    serverList = []
    server = await loop.create_server(
        lambda: LookupServerProtocol(serverList),
        '127.0.0.1', 8888)
    async with server:
        await server.serve_forever()
    pass


if __name__ == '__main__':
    asyncio.run(main())
