import asyncio
import json
import sys


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


async def main():
    # Get a reference to the event loop as we plan to use
    # low-level APIs.
    loop = asyncio.get_running_loop()

    on_con_lost = loop.create_future()
    transport, protocol = await loop.create_connection(
        lambda: ResourceProtocol('bursting.flv', on_con_lost),
        '127.0.0.1', 8888)

    # Wait until the protocol signals that the connection
    # is lost and close the transport.
    try:
        await on_con_lost
    finally:
        transport.close()


asyncio.run(main())
