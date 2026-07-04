# Multicast Video Streaming Project

This project is separate from the RTSP/RTP project. It implements a multicast MJPEG broadcaster and multicast clients.

## Files

- `Server.py`: reads an MJPEG file, packetizes frames, and multicasts them.
- `Client.py`: joins the multicast group and displays the video.
- `Packet.py`: custom packet format with fragmentation metadata.
- `VideoStream.py`: MJPEG frame reader.
- `movie.Mjpeg`: sample video.
- `REPORT.md`: short report for submission.

## Run

Install Pillow if needed:

```bash
pip install pillow
```

Start the multicast server:

```bash
python Server.py movie.Mjpeg
```

Start one or more clients:

```bash
python Client.py
```

Defaults:

- Multicast group: `239.1.1.1`
- Port: `5004`
- Frame rate: `20 FPS`

Optional examples:

```bash
python Server.py movie.Mjpeg --group 239.1.1.1 --port 5004 --fps 20
python Client.py --group 239.1.1.1 --port 5004
```
