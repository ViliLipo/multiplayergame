import asyncio
import json

IP = '127.0.0.1'
PORT = 8889


class ResourceServerProtocol(asyncio.Protocol):
    def connection_made(self, transport):
        self.transport = transport

    def data_received(self, data):
        message = data.decode()
        print(message)
        information = json.loads(message)
        try:
            filename = 'images/' + information["filename"]
            image = open(filename, 'rb')
            replyData = image.read()
            self.transport.write(replyData)
            image.close()
            self.transport.close()
            print('done')
        except FileNotFoundError:
            messageData = {'status': 404}
            self.transport.write(json.dumps(messageData).encode())
        except json.JSONDecodeError:
            messageData = {'status': 'illegal query'}
            self.transport.write(json.dumps(messageData).encode())



async def main():
    # Get a reference to the event loop as we plan to use
    # low-level APIs.
    loop = asyncio.get_running_loop()

    server = await loop.create_server(
        lambda: ResourceServerProtocol(),
        IP, PORT)

    async with server:
        await server.serve_forever()


asyncio.run(main())
