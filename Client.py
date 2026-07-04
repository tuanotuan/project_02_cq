import argparse
from io import BytesIO
import queue
import socket
import struct
import threading
import time
from tkinter import *
import tkinter.messagebox as messagebox

from PIL import Image, ImageTk

from Packet import MAX_DATAGRAM_SIZE, PacketDecodeError, decode_packet


MULTICAST_GROUP = "239.1.1.1"
MULTICAST_PORT = 5004
BUFFER_TIMEOUT = 2.0


class MulticastVideoClient:
    def __init__(self, master, group=MULTICAST_GROUP, port=MULTICAST_PORT, interface="0.0.0.0"):
        self.master = master
        self.group = group
        self.port = port
        self.interface = interface
        self.running = True
        self.socket = None
        self.membership = None

        self.frame_queue = queue.Queue(maxsize=90)
        self.fragment_buffers = {}
        self.last_completed_frame = None
        self.counted_lost_frames = set()

        self.packets_received = 0
        self.bytes_received = 0
        self.frames_decoded = 0
        self.frames_displayed = 0
        self.frames_lost = 0
        self.fragments_lost = 0
        self.corrupt_packets = 0
        self.started_at = time.monotonic()

        self._build_ui()
        self._open_socket()
        self.receiver = threading.Thread(target=self._receive_loop, daemon=True)
        self.receiver.start()
        self.master.after(20, self._display_loop)
        self.master.after(500, self._stats_loop)
        self.master.protocol("WM_DELETE_WINDOW", self.close)

    def _build_ui(self):
        self.master.geometry("980x620")
        self.master.rowconfigure(0, weight=1)
        self.master.columnconfigure(0, weight=1)

        self.label = Label(self.master, bg="black")
        self.label.grid(row=0, column=0, columnspan=2, padx=6, pady=6, sticky=N + S + W + E)

        self.stats_var = StringVar(value="Waiting for multicast stream...")
        self.stats = Label(self.master, textvariable=self.stats_var, anchor=W, justify=LEFT)
        self.stats.grid(row=1, column=0, padx=6, pady=4, sticky=W + E)

        self.close_button = Button(self.master, text="Leave", width=14, command=self.close)
        self.close_button.grid(row=1, column=1, padx=6, pady=4, sticky=E)

    def _open_socket(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass

        self.socket.bind(("", self.port))
        self.socket.settimeout(0.5)

        self.membership = socket.inet_aton(self.group) + socket.inet_aton(self.interface)
        self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, self.membership)

    def _receive_loop(self):
        while self.running:
            try:
                datagram, _ = self.socket.recvfrom(MAX_DATAGRAM_SIZE + 256)
            except socket.timeout:
                self._cleanup_stale_buffers()
                continue
            except OSError:
                break

            self.packets_received += 1
            self.bytes_received += len(datagram)

            try:
                packet = decode_packet(datagram)
            except PacketDecodeError:
                self.corrupt_packets += 1
                continue

            self._handle_packet(packet)
            self._cleanup_stale_buffers()

    def _handle_packet(self, packet):
        if packet.fragment_count == 1:
            self._enqueue_frame(packet.frame_id, packet.payload)
            return

        entry = self.fragment_buffers.setdefault(
            packet.frame_id,
            {
                "created_at": time.monotonic(),
                "fragment_count": packet.fragment_count,
                "parts": {},
            },
        )
        entry["parts"][packet.fragment_index] = packet.payload

        if len(entry["parts"]) == entry["fragment_count"]:
            frame = b"".join(entry["parts"][index] for index in range(entry["fragment_count"]))
            del self.fragment_buffers[packet.frame_id]
            self._enqueue_frame(packet.frame_id, frame)

    def _enqueue_frame(self, frame_id, frame):
        if self.last_completed_frame is not None:
            if frame_id <= self.last_completed_frame:
                return
            if frame_id > self.last_completed_frame + 1:
                for missing_frame in range(self.last_completed_frame + 1, frame_id):
                    self._mark_lost_frame(missing_frame)

        self.last_completed_frame = frame_id
        self.frames_decoded += 1

        try:
            self.frame_queue.put_nowait(frame)
        except queue.Full:
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                pass
            self.frame_queue.put_nowait(frame)

    def _cleanup_stale_buffers(self):
        now = time.monotonic()
        stale_ids = [
            frame_id
            for frame_id, entry in self.fragment_buffers.items()
            if now - entry["created_at"] > BUFFER_TIMEOUT
        ]

        for frame_id in stale_ids:
            entry = self.fragment_buffers.pop(frame_id)
            self.fragments_lost += entry["fragment_count"] - len(entry["parts"])
            self._mark_lost_frame(frame_id)

    def _mark_lost_frame(self, frame_id):
        if frame_id in self.counted_lost_frames:
            return

        self.counted_lost_frames.add(frame_id)
        self.frames_lost += 1

        if len(self.counted_lost_frames) > 10000:
            cutoff = max(self.counted_lost_frames) - 5000
            self.counted_lost_frames = {value for value in self.counted_lost_frames if value >= cutoff}

    def _display_loop(self):
        if not self.running:
            return

        frame = None
        try:
            while True:
                frame = self.frame_queue.get_nowait()
        except queue.Empty:
            pass

        if frame is not None:
            try:
                image = Image.open(BytesIO(frame))
                image.thumbnail((960, 540))
                photo = ImageTk.PhotoImage(image)
                self.label.configure(image=photo)
                self.label.image = photo
                self.frames_displayed += 1
            except OSError:
                self.corrupt_packets += 1

        self.master.after(20, self._display_loop)

    def _stats_loop(self):
        if not self.running:
            return

        elapsed = max(0.001, time.monotonic() - self.started_at)
        fps = self.frames_displayed / elapsed
        kbps = (self.bytes_received * 8 / elapsed) / 1000
        self.stats_var.set(
            f"group={self.group}:{self.port} | displayed={self.frames_displayed} | "
            f"decoded={self.frames_decoded} | fps={fps:.1f} | rate={kbps:.1f} Kbps | "
            f"lost_frames={self.frames_lost} | lost_fragments={self.fragments_lost} | "
            f"bad_packets={self.corrupt_packets}"
        )
        self.master.after(500, self._stats_loop)

    def close(self):
        if not self.running:
            return

        self.running = False
        if self.socket is not None:
            try:
                if self.membership is not None:
                    self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, self.membership)
            except OSError:
                pass

            try:
                self.socket.close()
            except OSError:
                pass
            self.socket = None

        self.master.destroy()


def parse_args():
    parser = argparse.ArgumentParser(description="MJPEG multicast video streaming client")
    parser.add_argument("--group", default=MULTICAST_GROUP, help="multicast group address")
    parser.add_argument("--port", type=int, default=MULTICAST_PORT, help="multicast UDP port")
    parser.add_argument("--interface", default="0.0.0.0", help="local interface address for group membership")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    root = Tk()
    root.title("Multicast Video Client")
    try:
        MulticastVideoClient(root, args.group, args.port, args.interface)
        root.mainloop()
    except OSError as exc:
        messagebox.showerror("Multicast Error", str(exc))
