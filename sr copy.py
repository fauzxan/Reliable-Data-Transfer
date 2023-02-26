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
    # self.set_timer()
    self.window = [b'']*config.WINDOW_SIZE
    self.expected_sequence_number = 0
    self.receiver_last_ack = b''
    self.is_receiver = True
    self.sender_lock = threading.Lock()
    self.timer = [None] * config.WINDOW_SIZE
    self.receiever_base = 0
    self.receive_buffer = {}


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
    
    # Set the timing thread object for that particular sequence number
    # self.set_timer(self.next_sequence_number)

    packet = util.make_packet(msg, config.MSG_TYPE_DATA, self.next_sequence_number)
    packet_data = util.extract_data(packet)
    self.window[self.next_sequence_number%config.WINDOW_SIZE] = packet
    util.log("Sending data: " + util.pkt_to_string(packet_data))
    self.network_layer.send(packet)   

    
    self.timer[self.next_sequence_number%config.WINDOW_SIZE] = self.set_timer(self.next_sequence_number%config.WINDOW_SIZE)
    self.timer[self.next_sequence_number%config.WINDOW_SIZE].start()

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
      seq_num = msg_data.seq_num

      # you stop the timer for that sequence number 
      util.log("Received ACK: " + util.pkt_to_string(msg_data))
      if self.timer[seq_num - self.sender_base].is_alive(): 
        self.timer[seq_num - self.sender_base].cancel()
        self.timer[seq_num - self.sender_base].join() # to block the parent thread from running after this
      if self.timer[seq_num - self.sender_base].finished:
        util.log(str(seq_num) + " has stopped")
      

      while self.timer[0] and self.timer[0].finished:
          self.sender_base += 1
          self.timer.pop(0)
          self.timer.append(None)
          time.sleep(0.11)
      
      util.log("Base of the window is currently at "+ str(self.sender_base))
        
        
      self.sender_lock.release()


    # If DATA message, assume its for receiver
    else:
      assert msg_data.msg_type == config.MSG_TYPE_DATA
      util.log("Received DATA: " + util.pkt_to_string(msg_data))
      seq_num = msg_data.seq_num
      # in gbn, the packet needs to be of the correct sequence number. 
      # in sr, the packet just needs to be in the range [send_base]
      if seq_num >= self.receiever_base and seq_num < (self.receiever_base+config.WINDOW_SIZE):

        # self.msg_handler(msg_data.payload)
        ack_pkt = util.make_packet(b'', config.MSG_TYPE_ACK, seq_num)
        self.network_layer.send(ack_pkt)
        util.log("Sent ACK: " + util.pkt_to_string(util.extract_data(ack_pkt)))
        
        index = seq_num%config.WINDOW_SIZE
        self.receive_buffer[index] = msg_data.payload
        
        if index == self.receiever_base: # if its receive base
          while index in self.receive_buffer:
            self.msg_handler(self.receive_buffer[index])
            util.log("Sent packet #"+str(index)+" to application above")
            index += 1
            self.receiever_base += 1
    
      elif seq_num in range(
        self.receiever_base - config.WINDOW_SIZE,
        self.receiever_base - 1
      ):
        ack_pkt = util.make_packet(b'', config.MSG_TYPE_ACK, seq_num)
        self.network_layer.send(ack_pkt)
        util.log("Sent ACK for a packet from prev window: " + util.pkt_to_string(util.extract_data(ack_pkt)))
        
      else:
        # ignore the packet, but with logs
        util.log("Recieved packet greater than window size: " + util.pkt_to_string(msg_data))
    return


  # Cleanup resources.
  def shutdown(self):
    if not self.is_receiver: self._wait_for_last_ACK()
    if self.timer[-1].is_alive(): self.timer[-1].cancel()
    util.log("Connection shutting down...")
    self.network_layer.shutdown()


  def _wait_for_last_ACK(self):
    while self.sender_base < self.next_sequence_number-1:
      util.log("Waiting for last ACK from receiver with sequence # "
               + str(int(self.next_sequence_number-1)) + ".")
      time.sleep(1)


  def _timeout(self, seq_num):
    util.log(f"Timeout for packet #{seq_num}. Resending packet with sequence #{seq_num}")
    # util.log("The timer: " + str(self.timer))
    self.sender_lock.acquire()
    
    if self.timer[seq_num].is_alive(): self.timer[seq_num].cancel()

    self.timer[seq_num] = self.set_timer(seq_num)
    
    # Select the packet from self.window, send it into the network layer
    pkt = self.window[seq_num]
    self.network_layer.send(pkt)
    
    # Restart the timer for the packet
    self.timer[seq_num].start()
    self.sender_lock.release()
    return
