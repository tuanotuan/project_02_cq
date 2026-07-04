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

On a two-machine Wi-Fi demo, bind multicast to the server Wi-Fi IPv4 address:

```bash
python Server.py movie.Mjpeg --interface 192.168.31.252 --fps 10 --repeat 2 --packet-delay-ms 1
```

Start one or more clients:

```bash
python Client.py
```

If the client has more than one network interface, bind the membership to the client Wi-Fi IPv4 address:

```bash
python Client.py --interface 192.168.31.185
```

Defaults:

- Multicast group: `239.1.1.1`
- Port: `5004`
- Frame rate: `20 FPS`

Use an SD MJPEG file first when demoing over Wi-Fi. HD/FHD multicast creates many UDP fragments per frame, and consumer Wi-Fi routers often drop multicast packets.

Optional examples:

```bash
python Server.py movie.Mjpeg --group 239.1.1.1 --port 5004 --fps 20
python Client.py --group 239.1.1.1 --port 5004
```
