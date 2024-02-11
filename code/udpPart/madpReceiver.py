import hashlib
import socket
import struct
import threading
import time
from utils import FileReassembler

PACKET_SIZE = 1434

if __name__ == "__main__":
    # IP and port of the receiver
    madpReceiverAddr = ('', 65432)
    outgoingSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    outgoingSocket.bind(madpReceiverAddr)
    serverAddress = ('172.17.0.3', 65433) # 172.17.0.2
    AckSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    expectedSeqNum = 0  # Expected sequence number of the next packet
    buffer = {} # Dictionary to hold out of order packets

    # File reassembler object serves for hashing and reconstructing the file 
    # from the chunks and the file ids.
    fileReassembler = FileReassembler()
    timeStart = None
    timeEnd = None
    started = False

    totalChunks = -2

    def advanceBuffer(seqNum):
        global expectedSeqNum, buffer, fileReassembler
        # If our buffer is empty we do not take action and simply return the seqNum
        # as this seqNum will already have incremented.
        if buffer == {}:
            # #print("Buffer empty")
            return seqNum
        else:
            #print("Buffer ", seqNum, " --->", end=" ")
            while True:
                # If our expected seqNum is in the buffer we deliver it to the file reassembler
                # and remove it from the buffer. Then we increment the seqNum and continue.
                # This is done until we reach a seqNum that is not in the buffer.
                # This increment is linear even though buffer is hashed. We are gaining time
                # by not iterating a list.
                # Also the argument of this function is the incremented seqNum meaning it is the expected one.
                if seqNum in buffer:
                    fileReassembler.add_chunk(*buffer[seqNum])
                    del buffer[seqNum]
                    seqNum += 1
                else:
                    break
            #print(seqNum)
            return seqNum # After advancing the buffer we return the new seqNum, namely, the expected one


    def madpReceiverMain():
        """
        This function handles the reception and processing of UDP packets.
        
        The function continuously receives packets and performs the following steps:
        1. Checks if the expected sequence number matches the termination sequence number (7230).
        2. If the sequence number matches, it calculates the time taken to receive all packets and sends an acknowledgment to the server.
        3. If the sequence number doesn't match, it checks the integrity of the received packet and adds it to the file reassembler.
        4. If the received sequence number is greater than the expected sequence number, it sends an acknowledgment for the last received packet and adds the new packet to the buffer.
        5. If the received sequence number is less than the expected sequence number, it continues to the next iteration.
        6. The function also handles keyboard interrupts by sending an empty acknowledgment packet and breaking the loop.
        
        Global Variables:
        - expectedSeqNum: Represents the expected sequence number of the next packet.
        - started: Indicates whether the reception has started or not.
        - timeStart: Stores the start time of the reception.
        - timeEnd: Stores the end time of the reception.
        - fileReassembler: An object used to reassemble the received packets into a file.
        """
        global expectedSeqNum, started, timeStart, timeEnd, fileReassembler, totalChunks
        while True:
            try:
                if expectedSeqNum  == totalChunks:
                    timeEnd = time.time()
                    AckSocket.sendto(b'', serverAddress)
                    break
                receivedPacket, _ = outgoingSocket.recvfrom(PACKET_SIZE)
                if not started:
                    started = True
                    timeStart = time.time()
                if receivedPacket == "" or receivedPacket == None:
                    break
                # #print("Network probed")

                # Below code serves for header unpacking and checksum calculation
                checkSum = struct.unpack('!16s', receivedPacket[0:16])[0]
                packedTime = struct.unpack('!d', receivedPacket[16:24])[0]
                packedSeqNum = struct.unpack('!H', receivedPacket[24:26])[0]
                packedFileId = struct.unpack('!H', receivedPacket[26:28])[0]
                packedChunkNum = struct.unpack('!H', receivedPacket[28:30])[0]
                packedTotalChunks = struct.unpack('!H', receivedPacket[30:32])[0]
                isLastChunk = struct.unpack('!?', receivedPacket[32:33])[0]
                isLarge = struct.unpack('!?', receivedPacket[33:34])[0]
                #print("Received packet : ", packedSeqNum, packedFileId, packedChunkNum, isLastChunk, isLarge)
                packet = receivedPacket[34:]
                calculatedCheckSum = hashlib.md5(packet).digest()
                #print("Expected seq num : ", expectedSeqNum)
                #print ("Received seq num : ", packedSeqNum)
                # #print("Received checksum : ", checkSum)
                # #print("Calculated checksum : ", calculatedCheckSum)
                totalChunks = packedTotalChunks
                # If the received packet is the expected one we check the checksum and add it to the file reassembler
                # Also we directly deliver it only if we have the expected packet.
                if packedSeqNum == expectedSeqNum: # If the received packet is the expected one
                    if checkSum == calculatedCheckSum:
                        # Directly deliver
                        fileReassembler.add_chunk(packedFileId, packedChunkNum, packet, isLastChunk, isLarge)
                        expectedSeqNum += 1

                        # Advance buffer and acknowledge the expected - 1
                        expectedSeqNum = advanceBuffer(expectedSeqNum)
                        acknowledgementPacket =  struct.pack('!d', packedTime) + struct.pack('!H', expectedSeqNum-1)
                        ackCheckSum = hashlib.md5(struct.pack('!H', expectedSeqNum-1)).digest()
                        ackCheckSum = struct.pack('!16s', ackCheckSum)
                        acknowledgementPacket = ackCheckSum + acknowledgementPacket
                        AckSocket.sendto(acknowledgementPacket, serverAddress)
                        #print("Sent ACK for packet : ", expectedSeqNum-1)
                        #print("Expected seq num : ", expectedSeqNum)


                # If the received packet is not the expected one we add it to the buffer so that sender don't
                # send it again. Also we send ACK for the last received packet. By doing this we are not losing
                # any packets. In the meanwhile we tell sender to send the expected packet by triggering Fast Retransmit.
                elif packedSeqNum > expectedSeqNum:
                    #print("----------------------")
                    #print("\tPacked seq num : ", packedSeqNum)
                    #print("\tExpected seq num : ", expectedSeqNum)
                    # #print("Packed Checksum : ", checkSum)
                    # #print("Calculated checksum : ", calculatedCheckSum)
                    #print("\tPacket buffered : ", packedSeqNum)
                    #print("----------------------")
                    # Instead of dropping packet we send ACK for the last received packet and add new packet to the buffer
                    if max(expectedSeqNum-1, 0) > 0:
                        acknowledgementPacket =  struct.pack('!d', packedTime) + struct.pack('!H', max(expectedSeqNum-1, 0))
                        ackCheckSum = hashlib.md5(struct.pack('!H', max(expectedSeqNum-1,0))).digest()
                        ackCheckSum = struct.pack('!16s', ackCheckSum)
                        acknowledgementPacket = ackCheckSum + acknowledgementPacket
                        AckSocket.sendto(acknowledgementPacket, serverAddress)
                        #print("Sent ACK for packet : ", max(expectedSeqNum-1, 0))
                    if packedSeqNum not in buffer: # If the packet is not in the buffer we add it
                        buffer[packedSeqNum] = (packedFileId, packedChunkNum, packet, isLastChunk, isLarge)
                else:
                    # If the received packet is less than the expected one we simply continue
                    # This is an optimization to not to process the packets that we already processed
                    continue        

            except KeyboardInterrupt:
                AckSocket.sendto(b'', serverAddress)
                break
        # Termination
        AckSocket.sendto(b'', serverAddress)                  
    
    

    madpReceiverMain()

    print("-----------------------")
    print("Total Time: ", timeEnd - timeStart)
    print("-----------------------")