import argparse
import math
import socket
import struct
import time

from Packet import MAX_PAYLOAD_SIZE, encode_packet
from VideoStream import VideoStream


MULTICAST_GROUP = "239.1.1.1"
MULTICAST_PORT = 5004
FPS = 20
TTL = 1


class MulticastVideoServer:
    def __init__(
        self,
        filename,
        group=MULTICAST_GROUP,
        port=MULTICAST_PORT,
        fps=FPS,
        ttl=TTL,
        interface="0.0.0.0",
        repeat=1,
        packet_delay_ms=0.0,
    ):
        self.filename = filename
        self.group = group
        self.port = port
        self.fps = fps
        self.ttl = ttl
        self.interface = interface
        self.repeat = max(1, repeat)
        self.packet_delay = max(0.0, packet_delay_ms / 1000.0)
        self.frame_id = 0
        self.bytes_sent = 0
        self.packets_sent = 0
        self.frames_sent = 0
        self.video = VideoStream(filename)
        self.socket = self._create_socket()

    def _create_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, struct.pack("B", self.ttl))
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
        if self.interface != "0.0.0.0":
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(self.interface))
        return sock

    def run(self):
        frame_delay = 1.0 / self.fps
        next_frame_at = time.perf_counter()
        last_report_at = time.perf_counter()

        print(f"Multicast server streaming {self.filename}")
        print(
            f"Destination: {self.group}:{self.port}, FPS: {self.fps}, TTL: {self.ttl}, "
            f"interface: {self.interface}, repeat: {self.repeat}"
        )

        try:
            while True:
                frame = self.video.next_frame_loop()
                if not frame:
                    raise RuntimeError("video has no readable MJPEG frames")

                self._send_frame(frame)
                self.frames_sent += 1

                now = time.perf_counter()
                if now - last_report_at >= 5:
                    self._print_stats(now - last_report_at)
                    last_report_at = now

                next_frame_at += frame_delay
                sleep_for = next_frame_at - time.perf_counter()
                if sleep_for > 0:
                    time.sleep(sleep_for)
                else:
                    next_frame_at = time.perf_counter()
        except KeyboardInterrupt:
            print("\nServer stopped")
        finally:
            self.video.close()
            self.socket.close()

    def _send_frame(self, frame):
        self.frame_id = (self.frame_id + 1) & 0xFFFFFFFF
        timestamp_ms = int(time.time() * 1000) & 0xFFFFFFFF
        fragment_count = max(1, math.ceil(len(frame) / MAX_PAYLOAD_SIZE))

        for fragment_index in range(fragment_count):
            start = fragment_index * MAX_PAYLOAD_SIZE
            payload = frame[start:start + MAX_PAYLOAD_SIZE]
            packet = encode_packet(self.frame_id, timestamp_ms, fragment_index, fragment_count, payload)
            for _ in range(self.repeat):
                self.socket.sendto(packet, (self.group, self.port))
                self.packets_sent += 1
                self.bytes_sent += len(packet)
                if self.packet_delay > 0:
                    time.sleep(self.packet_delay)

    def _print_stats(self, elapsed):
        mbps = (self.bytes_sent * 8 / elapsed) / 1_000_000
        print(
            f"stats: frames={self.frames_sent} packets={self.packets_sent} "
            f"bytes={self.bytes_sent} rate={mbps:.2f} Mbps"
        )
        self.bytes_sent = 0
        self.packets_sent = 0


def parse_args():
    parser = argparse.ArgumentParser(description="MJPEG multicast video streaming server")
    parser.add_argument("filename", help="MJPEG video file")
    parser.add_argument("--group", default=MULTICAST_GROUP, help="multicast group address")
    parser.add_argument("--port", type=int, default=MULTICAST_PORT, help="multicast UDP port")
    parser.add_argument("--fps", type=int, default=FPS, help="frames per second")
    parser.add_argument("--ttl", type=int, default=TTL, help="multicast TTL")
    parser.add_argument("--interface", default="0.0.0.0", help="local interface address used to send multicast")
    parser.add_argument("--repeat", type=int, default=1, help="send each packet this many times")
    parser.add_argument("--packet-delay-ms", type=float, default=0.0, help="delay between repeated packets")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    server = MulticastVideoServer(
        args.filename,
        args.group,
        args.port,
        args.fps,
        args.ttl,
        args.interface,
        args.repeat,
        args.packet_delay_ms,
    )
    server.run()
