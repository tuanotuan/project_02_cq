import os


class VideoStream:
    SOI = b"\xff\xd8"
    EOI = b"\xff\xd9"

    def __init__(self, filename):
        self.filename = self._resolve_path(filename)
        try:
            self.file = open(self.filename, "rb")
        except OSError:
            raise IOError(f"Cannot open video file: {filename}")

        self.frame_number = 0
        self.buffer = b""
        self.mode = self._detect_mode()

    def _resolve_path(self, filename):
        if os.path.exists(filename):
            return filename

        local_path = os.path.join(os.path.dirname(__file__), filename)
        if os.path.exists(local_path):
            return local_path

        return filename

    def _detect_mode(self):
        head = self.file.read(8)
        self.file.seek(0)
        if len(head) >= 5 and head[:5].isdigit():
            return "length-prefixed"
        return "jpeg-markers"

    def next_frame(self):
        if self.mode == "length-prefixed":
            return self._next_length_prefixed_frame()
        return self._next_marker_delimited_frame()

    def next_frame_loop(self):
        frame = self.next_frame()
        if frame:
            return frame

        self.rewind()
        return self.next_frame()

    def _next_length_prefixed_frame(self):
        length_bytes = self.file.read(5)
        if not length_bytes or len(length_bytes) < 5:
            return b""

        try:
            frame_length = int(length_bytes)
        except ValueError:
            return b""

        frame = self.file.read(frame_length)
        if len(frame) != frame_length:
            return b""

        self.frame_number += 1
        return frame

    def _next_marker_delimited_frame(self):
        while self.SOI not in self.buffer:
            chunk = self.file.read(8192)
            if not chunk:
                return b""
            self.buffer += chunk

        start = self.buffer.find(self.SOI)
        if start > 0:
            self.buffer = self.buffer[start:]

        while True:
            end = self.buffer.find(self.EOI, len(self.SOI))
            if end != -1:
                frame = self.buffer[:end + len(self.EOI)]
                self.buffer = self.buffer[end + len(self.EOI):]
                self.frame_number += 1
                return frame

            chunk = self.file.read(8192)
            if not chunk:
                return b""
            self.buffer += chunk

    def rewind(self):
        self.file.seek(0)
        self.buffer = b""
        self.frame_number = 0

    def close(self):
        self.file.close()
