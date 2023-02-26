# Reliable-Data-Transfer
Exploring the usage of Stop and Wait, Give Back N and Selective Repeat Protocols
This code has been adapted from https://github.com/z9z/reliable_data_transfer (author Susanna Edens),  
where you could find the implementation of a simple stop-and-wait (RDT 3.0 in the A Top-Down Approach) 
protocol and the implementation of a Go-Back-N (GBN) protocol

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
1. **Data received from above.** When data is received from above, the SR sender
checks the next available sequence number for the packet. If the sequence
number is within the sender’s window, the data is packetized and sent; otherwise
it is either buffered or returned to the upper layer for later transmission,
as in GBN.

```python3
def send(self, msg):
    self.is_receiver = False
    if self.next_sequence_number < (self.sender_base + config.WINDOW_SIZE):
      self._send_helper(msg)
      return True
    else:
      util.log("Window is full. App data rejected.")
      time.sleep(2)
      return False


  # Helper fn for thread to send the next packet
  def _send_helper(self, msg):
    self.sender_lock.acquire()

    # Sequence number will only fall within 0...WINDOW_SIZE
    

    # Make the packet and send the data 
    packet = util.make_packet(msg, config.MSG_TYPE_DATA, self.next_sequence_number)
    util.log("Sending data for packet #"+str(self.next_sequence_number))
    self.network_layer.send(packet) 

    # Start the appropirate timer and assign the value in the appropriate window index
    self.timer[self.next_sequence_number] = self.set_timer(self.next_sequence_number)
    self.timer[self.next_sequence_number].start()
    self.window[self.next_sequence_number] = packet

    # Increment the sequence number
    self.next_sequence_number += 1

    self.sender_lock.release()
    return

```



2. **Timeout.** Timers are again used to protect against lost packets. However, each
packet must now have its own logical timer, since only a single packet will
be transmitted on timeout. A single hardware timer can be used to mimic the
operation of multiple logical timers.

```python3
def _timeout(self, seq_num):
    
    self.sender_lock.acquire()
    util.log(f"Timeout for packet #{seq_num}. Resending packet...")

    # If the timer is still running. You do not need to join this with the parent thread
    if self.timer[seq_num] and self.timer[seq_num].is_alive(): 
      self.timer[seq_num].cancel()
      try:
        self.timer[seq_num].join()
      except (RuntimeError):
        pass
      

      # Only carry out the following, if the timer at that index has properly finished.
      if self.timer[seq_num].finished:
        
        
        # create new thread timer here
        self.timer[seq_num] = self.set_timer(seq_num)

        # Retrieve the packet data from the window and send it into the network layer
        packet = self.window[seq_num]
        self.network_layer.send(packet)

        util.log("Retransmitted packet #"+str(seq_num))

        # Start the time once sent
        self.timer[seq_num].start()

    # If sequence number is not found      
    else:
      self.timer[seq_num] = self.set_timer(seq_num)
      
      # Retreive packet data from the window and send it into the network layer
      packet = self.window[seq_num]
      self.network_layer.send(packet)

      util.log("Retransmitted packet #"+str(seq_num))
      
      # Start the time once sent
      self.timer[seq_num].start()
    
    self.sender_lock.release()
    return

```

3. **ACK received.** If an ACK is received, the SR sender marks that packet as
having been received, provided it is in the window. If the packet’s sequence
number is equal to send_base, the window base is moved forward to the
unacknowledged packet with the smallest sequence number. If the window
moves and there are untransmitted packets with sequence numbers that now
fall within the window, these packets are transmitted.

```python3
 def handle_arrival_msg(self):
    msg = self.network_layer.recv()
    msg_data = util.extract_data(msg)

    if(msg_data.is_corrupt):
      return
      
    # If ACK message, assume its for sender
    if msg_data.msg_type == config.MSG_TYPE_ACK:
      self.sender_lock.acquire()

      
      util.log("ACK recieved for packet #"+str(msg_data.seq_num))


      # If the timer is running in the respective timer index, then stop it, and also 'join' the thread with the parent process
      if self.timer[msg_data.seq_num] and self.timer[msg_data.seq_num].is_alive():
        self.timer[msg_data.seq_num].cancel()
        try:
          self.timer[msg_data.seq_num].join()
        except (RuntimeError):
          pass

        if self.timer[msg_data.seq_num].finished:
          util.log("Sequence number "+str(msg_data.seq_num)+" has been terminated.")
      
      # Reset that index in the window to free up space.
      # You may also choose to delete it completely. But for logging purposes, we will retain this information.
      self.window[msg_data.seq_num] = b''
      
      # If the sender base is at the same  position as the sequence number, you may update the sender
      # base to the position of the earliest unack-ed packet
      if msg_data.seq_num == self.sender_base:
        # Move the base as long as timer is not a NONE object and the timer for that index is finished 
        i = self.sender_base
        while self.timer[i] and not self.timer[i].is_alive():
          # You may delete the timer at index i. But we will retain the information for logging purposes.
          self.timer[i] = None
          self.sender_base += 1
          i += 1
          if i not in self.timer:
            break
        
        util.log("The base has now been moved to: "+str(self.sender_base))
      util.log("State of window now: "+ str(self.window))

      self.sender_lock.release()

```


### Receiver side
1. **Packet with sequence number in [rcv_base, rcv_base+N-1]is correctly
received.** In this case, the received packet falls within the receiver’s window
and a selective ACK packet is returned to the sender. If the packet was not
previously received, it is buffered. If this packet has a sequence number equal to
the base of the receive window, then this packet,
and any previously buffered and consecutively numbered (beginning with
rcv_base) packets are delivered to the upper layer. The receive window is
then moved forward by the number of packets delivered to the upper layer. 

```python3
# This method also falls within the function: handle_arrival_msg()
    # If DATA message, assume its for receiver
    else:
      assert msg_data.msg_type == config.MSG_TYPE_DATA
      # self.sender_lock.acquire()

      util.log("Received packet #"+ str(msg_data.seq_num))

      # Case 1: If the seq number falls within the window 
      if msg_data.seq_num >= self.receiever_base and msg_data.seq_num < self.receiever_base + config.WINDOW_SIZE:
        # Make ACK packet and send it
        ack_pkt = util.make_packet(b'', config.MSG_TYPE_ACK, msg_data.seq_num)
        self.network_layer.send(ack_pkt)
        util.log("Sent ACK: " + util.pkt_to_string(util.extract_data(ack_pkt)))

        # Store the paacket in the buffer
        self.receive_buffer[msg_data.seq_num] = msg_data.payload

        # If the seq_num is at the receiver base, then send all the packets upto the first unsent packet. 
        # (The first unsent packet will not be present in the dict , which is when we break)
        if msg_data.seq_num == self.receiever_base:
          i = self.receiever_base
          while self.receive_buffer[i]:
            self.msg_handler(self.receive_buffer[i])
            util.log("Sent packet #"+str(i)+" to application layer")
            i += 1
            self.receiever_base += 1
            if i not in self.receive_buffer:
              break


```

2. **Packet with sequence number in [rcv_base-N, rcv_base-1]is correctly
received.** In this case, an ACK must be generated, even though this is a
packet that the receiver has previously acknowledged.
3. Otherwise. Ignore the packet.

```python3
      # Case 2: If the seq number is less than the receiver base
      elif msg_data.seq_num < self.receiever_base:
        # Make ACK packet and send it
        ack_pkt = util.make_packet(b'', config.MSG_TYPE_ACK, msg_data.seq_num)
        self.network_layer.send(ack_pkt)
        util.log("Sent ACK: " + util.pkt_to_string(util.extract_data(ack_pkt)))
      
      # Case 3: If the seq number is greater than the window
      else:
        pass
```
## 
