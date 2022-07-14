import logging
import struct
from typing import List


class Communicator:
    def memory_read(self, addr: int, size: int) -> bytes:
        raise NotImplementedError("Abstract.")

    def memory_write(self, addr: int, data: bytes) -> None:
        raise NotImplementedError("Abstract.")

    def call(self, addr: int, numbytes_return: int, args: List[int]) -> int:
        raise NotImplementedError("Abstract.")


class CommunicatorStub(Communicator):
    def __init__(self):
        super().__init__()
        self.memory = {}

    def memory_read(self, addr: int, size: int) -> bytes:
        result = bytes([self.memory.get(location, 0) for location in range(addr, addr + size)])
        logging.getLogger(__name__).debug(f"PyGti2Command.memory_read {addr}, {size} -> {result.hex()}")
        return result

    def memory_write(self, addr: int, data: bytes) -> None:
        logging.getLogger(__name__).debug(f"PyGti2Command.memory_write {addr}, {data.hex()}")
        for i, b in enumerate(data):
            self.memory[addr + i] = b


class Gti2Communicactor(Communicator):
    def marshal_long(self, x: int) -> bytes:
        return x.to_bytes(self.sizeof_long, "big")

    def unmarshal_long(self, x: bytes) -> int:
        return int.from_bytes(x, "big")

    def command(self, cmd, data, expected):
        self.write(struct.pack("!HH", cmd, len(data)) + data)
        response = self.read(2 + expected)
        if response[:2] != b"OK":
            raise Exception("Command did not respond sucessfully.")
        return response[2:]

    def call(self, addr: int, numbytes_return: int, args: List[int]) -> int:
        if numbytes_return > 0:
            numbytes_return = self.sizeof_long
        callargs = (
            self.marshal_long(addr),
            struct.pack("!HH", numbytes_return, len(args)),
            b"".join(self.marshal_long(arg) for arg in args),
        )
        result = self.command(3, b"".join(callargs), numbytes_return)
        logging.getLogger(__name__).debug(f"PyGti2Command.call {callargs}, {numbytes_return} -> {result}")
        return self.unmarshal_long(result)

    def memory_read(self, addr: int, size: int) -> bytes:
        logging.getLogger(__name__).debug(f"PyGti2Command.memory_read 0x{addr:08x}, {size} -> ...")
        result = self.command(
            1,
            self.marshal_long(addr) + self.marshal_long(size),
            size,
        )
        logging.getLogger(__name__).debug(f"PyGti2Command.memory_read ... -> {result.hex()}")
        return result

    def memory_write(self, addr: int, data: bytes) -> None:
        if len(data) == 0:
            return
        logging.getLogger(__name__).debug(f"PyGti2Command.memory_write 0x{addr:08x}, {data.hex()}")
        return self.command(2, self.marshal_long(addr) + data, 0)

    def echo(self, data: bytes) -> bytes:
        result = self.command(0, data, len(data))
        logging.getLogger(__name__).debug(f"PyGti2Command.echo {data} -> {result}")
        return result


class Gti2SerialCommunicator(Gti2Communicactor):
    def __init__(self, port, baud, sizeof_long):
        self.sizeof_long = sizeof_long
        import serial

        self.ser = serial.Serial(port, baud)
        while True:
            self.ser.read_all()
            self.ser.timeout = 0.5
            if self.echo(b"hello") == b"hello":
                break
        self.ser.timeout = None

    def read(self, length):
        data = self.ser.read(length)
        if len(data) != length:
            raise TimeoutError("Device took too long to respond.")
        return data

    def write(self, data):
        self.ser.write(data)


class Gti2SocketCommunicator(Gti2Communicactor):
    def __init__(self, address, sizeof_long):
        self.sizeof_long = sizeof_long
        import socket

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect(address)
        if self.echo(b"hello") != b"hello":
            raise Exception("Something went wrong.")

    def read(self, length):
        data = b""
        while len(data) < length:
            data += self.sock.recv(length - len(data))
        return data

    def write(self, data):
        self.sock.sendall(data)

    def __del__(self):
        self.sock.close()
