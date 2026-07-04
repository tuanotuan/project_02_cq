# Report - Multicast Video Streaming

## Architecture

The multicast project is independent from the RTSP/RTP project. It does not use RTSP, RTP, TCP mode selection, or separate control and media channels.

The server reads MJPEG frames from disk and sends them to multicast group `239.1.1.1:5004`. Multiple clients can join the same multicast group and receive the same stream at the same time.

```text
Server -> 239.1.1.1:5004 -> Client 1
                         -> Client 2
                         -> Client N
```

## Packet Format

Each UDP datagram uses a custom 24-byte header:

```text
magic(4) | version(1) | flags(1) | header_size(2)
frame_id(4) | timestamp_ms(4)
fragment_index(2) | fragment_count(2) | payload_size(4)
payload(...)
```

Large MJPEG frames are split into multiple fragments. The client reassembles all fragments with the same `frame_id` before decoding the JPEG frame.

## Server Implementation

The server:

- Opens the MJPEG file.
- Reads one frame at a time.
- Splits frames into multicast packets when needed.
- Sends packets to the multicast group.
- Streams at approximately 20 FPS.
- Rewinds automatically and repeats the video when the file ends.
- Prints periodic throughput statistics.
- Can bind the outgoing multicast stream to a specific Wi-Fi interface with `--interface`.
- Can repeat packets for unstable Wi-Fi demos with `--repeat`.

Run:

```bash
python Server.py movie.Mjpeg
```

For a two-machine Wi-Fi demo:

```bash
python Server.py movie.Mjpeg --interface <SERVER_WIFI_IPV4> --fps 10 --repeat 2 --packet-delay-ms 1
```

## Client Implementation

The client:

- Joins multicast group `239.1.1.1:5004`.
- Receives UDP datagrams.
- Validates the custom header.
- Reassembles fragmented frames.
- Displays frames using Tkinter and Pillow.
- Leaves the multicast group when the window closes.
- Tracks displayed frames, decoded frames, bitrate, lost frames, lost fragments, and corrupted packets.

Run:

```bash
python Client.py
```

If the client has multiple interfaces:

```bash
python Client.py --interface <CLIENT_WIFI_IPV4>
```

## Multiple Clients And Loss Detection

Because the server sends to a multicast group, any number of clients on the network can join without creating new server connections.

Loss detection is based on:

- Missing `frame_id` values.
- Fragment buffers that time out before all fragments arrive.
- Invalid or corrupted custom packet headers.

## Testing

Test steps:

1. Start the server.
2. Start one client and verify the video is displayed.
3. Start a second client and verify both clients show the same stream.
4. Close a client and verify it leaves the group without stopping the server.
5. Observe client statistics for received frames, loss, and corrupted packets.
