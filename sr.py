import config
import threading
import time
import udt
import util


class Sender:
  def __init__(self, ):
    pass
  pass


class Receiver:
  pass


# Go-Back-N reliable transport protocol.
class SelectiveRepeat:

  NO_PREV_ACK_MSG = "Don't have previous ACK to send, will wait for server to timeout."

  # "msg_handler" is used to deliver messages to application layer
  def __init__(self, local_port, remote_port, msg_handler):
    util.log("Starting up `Selective Repeat` protocol ... ")
    self.network_layer = udt.NetworkLayer(local_port, remote_port, self)
    self.msg_handler = msg_handler
    self.sender_base = 0
    self.next_sequence_number = 0
    self.window = {}
    self.sender_lock = threading.Lock()
    self.timer = {}
    self.receiever_base = 0
    self.receive_buffer = {}
    self.is_receiver = True


  def set_timer(self, seq_num):
    # There needs to be a thread for each and every packet in the window.

    # [self.sender_base ... self.sender_base + config.WINDOW_SIZE - 1]
    # create a thread for that sequence number
   return threading.Timer((config.TIMEOUT_MSEC/1000.0), self._timeout, {seq_num}) 


  # "send" is called by application. Return true on success, false otherwise.
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


  # "handler" to be called by network layer when packet is ready.
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
      # But for logging purposes, we will retain this information.
      self.window[msg_data.seq_num] = b''
      
      # If the sender base is at the same  position as the sequence number, 
      # you may update the sender base to the position of the earliest unack-ed packet
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

        # If the seq_num is at the receiver base, then send all the packets upto the first unsent packet
        # (The first unsent packet will not be present in the dict, which is when we break)
        if msg_data.seq_num == self.receiever_base:
          i = self.receiever_base
          while self.receive_buffer[i]:
            self.msg_handler(self.receive_buffer[i])
            util.log("Sent packet #"+str(i)+" to application layer")
            i += 1
            self.receiever_base += 1
            if i not in self.receive_buffer:
              break


      # Case 2: If the seq number is less than the receiver base
      elif msg_data.seq_num < self.receiever_base:
        # Make ACK packet and send it
        ack_pkt = util.make_packet(b'', config.MSG_TYPE_ACK, msg_data.seq_num)
        self.network_layer.send(ack_pkt)
        util.log("Sent ACK: " + util.pkt_to_string(util.extract_data(ack_pkt)))
      
      # Case 3: If the seq number is greater than the window
      else:
        pass

      # self.sender_lock.release()
     
    return


  # Cleanup resources.
  def shutdown(self):
    if not self.is_receiver: self._wait_for_last_ACK()
    for i in self.timer.values():
      if i:
        i.cancel()
    util.log("Connection shutting down...")
    self.network_layer.shutdown()


  def _wait_for_last_ACK(self):
    # Just wait for all the timers to come to a stop. The algorithm will make the value None if stopped
    for value in self.timer.values():
      if value:
        time.sleep(1)
    util.log("\nFinal state of the window: "+str(self.window))
    util.log("\nFinal state of the timers: "+str(self.timer))



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
