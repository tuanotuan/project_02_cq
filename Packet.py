import struct
from dataclasses import dataclass


MAGIC = b"MCVS"
VERSION = 1
FLAG_LAST_FRAGMENT = 1
HEADER_FORMAT = "!4sBBHIIHHI"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
MAX_DATAGRAM_SIZE = 1400
MAX_PAYLOAD_SIZE = MAX_DATAGRAM_SIZE - HEADER_SIZE


class PacketDecodeError(ValueError):
    pass


@dataclass(frozen=True)
class MulticastPacket:
    frame_id: int
    timestamp_ms: int
    fragment_index: int
    fragment_count: int
    payload: bytes
    is_last_fragment: bool


def encode_packet(frame_id, timestamp_ms, fragment_index, fragment_count, payload):
    """Encode one custom multicast video packet."""
    if fragment_count <= 0:
        raise ValueError("fragment_count must be positive")
    if fragment_index < 0 or fragment_index >= fragment_count:
        raise ValueError("fragment_index out of range")
    if fragment_count > 0xFFFF:
        raise ValueError("too many fragments for one frame")
    if len(payload) > MAX_PAYLOAD_SIZE:
        raise ValueError("payload exceeds multicast packet payload limit")

    flags = FLAG_LAST_FRAGMENT if fragment_index == fragment_count - 1 else 0
    header = struct.pack(
        HEADER_FORMAT,
        MAGIC,
        VERSION,
        flags,
        HEADER_SIZE,
        frame_id & 0xFFFFFFFF,
        timestamp_ms & 0xFFFFFFFF,
        fragment_index & 0xFFFF,
        fragment_count & 0xFFFF,
        len(payload),
    )
    return header + payload


def decode_packet(datagram):
    """Decode and validate one custom multicast video packet."""
    if len(datagram) < HEADER_SIZE:
        raise PacketDecodeError("packet too short")

    magic, version, flags, header_size, frame_id, timestamp_ms, fragment_index, fragment_count, payload_size = struct.unpack(
        HEADER_FORMAT, datagram[:HEADER_SIZE]
    )

    if magic != MAGIC:
        raise PacketDecodeError("invalid magic")
    if version != VERSION:
        raise PacketDecodeError("unsupported version")
    if header_size != HEADER_SIZE:
        raise PacketDecodeError("invalid header size")
    if fragment_count <= 0:
        raise PacketDecodeError("invalid fragment count")
    if fragment_index >= fragment_count:
        raise PacketDecodeError("fragment index out of range")
    if payload_size != len(datagram) - HEADER_SIZE:
        raise PacketDecodeError("invalid payload size")

    payload = datagram[HEADER_SIZE:]
    return MulticastPacket(
        frame_id=frame_id,
        timestamp_ms=timestamp_ms,
        fragment_index=fragment_index,
        fragment_count=fragment_count,
        payload=payload,
        is_last_fragment=bool(flags & FLAG_LAST_FRAGMENT),
    )
