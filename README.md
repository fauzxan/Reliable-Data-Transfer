# Reliable-Data-Transfer
Exploring the usage of Stop and Wait, Give Back N and Selective Repeat Protocols
This code has been adapted from https://github.com/z9z/reliable_data_transfer (author Susanna Edens),  where you could find the implementation of a simple stop-and-wait (RDT 3.0 in the A Top-Down Approach) protocol and the implementation of a Go-Back-N (GBN) protocol

## Setup and testing
Open the project directory on terminal and type in the following:
```ubuntu22.0
python demo_receiver.py [ss | sr | gbn]
python demo_sender.py ss [ss | sr | gbn]
```

- ss refers to stop and wait protocol
- sr refers to selective repeat protocol
- gbn refers to go back n protocol

## Selective repeat protocol
The following algorithm has been implemented from the textbook:
### Sender side
1. Data received from above. When data is received from above, the SR sender
checks the next available sequence number for the packet. If the sequence
number is within the sender’s window, the data is packetized and sent; otherwise
it is either bu!ered or returned to the upper layer for later transmission,
as in GBN.
2. Timeout. Timers are again used to protect against lost packets. However, each
packet must now have its own logical timer, since only a single packet will
be transmitted on timeout. A single hardware timer can be used to mimic the
operation of multiple logical timers [Varghese 1997].
3. ACK received. If an ACK is received, the SR sender marks that packet as
having been received, provided it is in the window. If the packet’s sequence
number is equal to send_base, the window base is moved forward to the
unacknowledged packet with the smallest sequence number. If the window
moves and there are untransmitted packets with sequence numbers that now
fall within the window, these packets are transmitted.


### Receiver side
1. Packet with sequence number in [rcv_base, rcv_base+N-1]is correctly
received. In this case, the received packet falls within the receiver’s window
and a selective ACK packet is returned to the sender. If the packet was not
previously received, it is bu!ered. If this packet has a sequence number equal to
the base of the receive window (rcv_base in Figure 3.22), then this packet,
and any previously bu!ered and consecutively numbered (beginning with
rcv_base) packets are delivered to the upper layer. The receive window is
then moved forward by the number of packets delivered to the upper layer. As
an example, consider Figure 3.26. When a packet with a sequence number of
rcv_base=2 is received, it and packets 3, 4, and 5 can be delivered to the
upper layer.
2. Packet with sequence number in [rcv_base-N, rcv_base-1]is correctly
received. In this case, an ACK must be generated, even though this is a
packet that the receiver has previously acknowledged.
3. Otherwise. Ignore the packet.

