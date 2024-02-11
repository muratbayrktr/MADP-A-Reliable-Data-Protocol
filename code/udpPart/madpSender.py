import hashlib
import socket
import struct
import threading
import time

# Settings for file I/O
DATA_FOLDER = '../app/objects' 
PACKET_SIZE = 1400


def readData():
    """
    Reads the data from files and returns a dictionary containing the file names as keys and the file contents as values.
    
    Returns:
        dict: A dictionary containing the file names as keys and the file contents as values.
    """
    data = {}
    for i in range(10):
        with open(DATA_FOLDER + f'/small-{i}.obj', 'rb') as f:
            data[f'small-{i}.obj'] = f.read()
    for i in range(10):
        with open(DATA_FOLDER + f'/large-{i}.obj', 'rb') as f:
            data[f'large-{i}.obj'] = f.read()        
    return data

def chunks(data):
    """
    Split the data into smaller chunks for transmission.

    Args:
        data (dict): A dictionary containing file data.

    Returns:
        tuple: A tuple containing the chunked data and the total number of chunks.
    """
    chunked = []
    for i in range(10):
        fileData = data[f'small-{i}.obj']
        for i in range(0, len(fileData), PACKET_SIZE):
            chunk = fileData[i:i + PACKET_SIZE]
            chunked.append(chunk)
        data[f'small-{i}.obj'] = chunked
    for i in range(10):
        fileData = data[f'large-{i}.obj']
        for i in range(0, len(fileData), PACKET_SIZE):
            chunk = fileData[i:i + PACKET_SIZE]
            chunked.append(chunk)
        data[f'large-{i}.obj'] = chunked
    return chunked, len(chunked)

def interleaved_chunks(data):
    """
    Interleaves the data into chunks for transmission. 1 small 1 large 1 small 1 large ...

    Args:
        data (dict): A dictionary containing the data to be chunked.

    Returns:
        tuple: A tuple containing the chunked data and the total number of chunks.
    """
    chunked = []
    for j in range(10):
        for size in ['small', 'large']:
            tempchunked = []
            fileData = data[f'{size}-{j}.obj']
            file_id = j
            is_large = size == 'large'
            for i in range(0, len(fileData), PACKET_SIZE):
                chunk = fileData[i:i + PACKET_SIZE]
                chunk_num = i // PACKET_SIZE
                tempchunked.append((file_id, chunk_num, chunk, 0, is_large)) # 0 means not last chunk
            tempchunked[-1] = (file_id, chunk_num, chunk, 1, is_large)
            chunked += tempchunked

    return chunked, len(chunked)


if __name__ == "__main__":
    # Define the address and port of the MADP receiver
    madpReceiverAddr = ('172.17.0.2', 65432) # 172.17.0.3
    outgoingSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    serverAddress = ('', 65433)
    receiverSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiverSocket.bind(serverAddress)
    # Read the data from the files
    data = readData()
    # Divide it into chunks
    (chunkedData, totalChunks) = interleaved_chunks(data); # #print(totalChunks)

    # Sequence number of the next packet to be sent (starts at 0)
    # Sender starts incrementing this sequence number and sends the packet
    # Sender window is measured between the base and the sequence number, so the window size is 1 at the beginning
    seqNum = 0
    base = 0
    # This is explained in the paper and fixed to 64000 to match the TCP standard
    # Again below, we employed flow control and congestion avoidance; however, later 
    # we found out that fixing windowSize to 64000 is doing great and there was no
    # significant improvement for the cases.
    windowSize = 64000
    congestionWindowSize = 1
    ssthresh = 64000  # Slow start threshold

    # Duplicate ACK count
    # Used for fast retransmit,
    dupACKcount = 0
    lastACK = 0

    # Timeout interval in seconds, initially set to 1 second
    # By the book we calculate the timeout interval using the sampleRTT and devRTT
    timeoutInterval = 1.0
    estimatedRTT = timeoutInterval
    devRTT = 0

    # Locks and conditions
    lockB = threading.Lock()
    lockT = threading.Lock()
    lockD = threading.Lock()
    condB = threading.Condition(lockB)

    def MADPAckHandler():
        """
        This function handles the acknowledgment (ACK) packets received by the sender.

        It continuously listens for ACK packets from the receiver and performs the following tasks:
        - Verifies the integrity of the ACK packet using checksum.
        - Updates the base sequence number if a new ACK is received.
        - Handles duplicate ACKs and performs fast retransmit if necessary.
        - Adjusts the congestion window size based on the received ACKs.
        - Updates the timeout interval for retransmission based on the sample round-trip time (RTT).

        Globals used:
        - base: The base sequence number of the packets sent.
        - timer: The timer used for retransmission.
        - dupACKcount: The count of duplicate ACKs received.
        - timeoutInterval: The current timeout interval for retransmission.
        - congestionWindowSize: The current congestion window size.
        - ssthresh: The slow start threshold for congestion control.

        Note: This function runs in an infinite loop until termination condition is triggered.

        """
        
        global base, timer, dupACKcount, timeoutInterval, congestionWindowSize, ssthresh
        while True:
            try:
                packet  = receiverSocket.recv(1024)
                # ##print("Received ACK", packet)
                if packet == b'' or packet == None:
                    break

                # extract checksum, time, and seqNum with struct unpack
                checkSum = struct.unpack('!16s', packet[0:16])[0]
                packedTime = struct.unpack('!d', packet[16:24])[0]
                packedSeqNum = struct.unpack('!H', packet[24:26])[0]
                calculatedCheckSum = hashlib.md5(struct.pack('!H', packedSeqNum)).digest()

                if checkSum == calculatedCheckSum: # Checksum is correct
                    with lockB: # Update base
                        #print("Received ACK for packet:", packedSeqNum,"SeqNum:",seqNum, "Base: ",base, "--->", end=" ")
                        # If our ack is newer than base, update base. This basically means that we received an ACK for further packet
                        # The receiver is telling us that it received the packet up to this ack and requires the ack+1 now.
                        if packedSeqNum + 1 > base:  
                            base = packedSeqNum + 1 # We advance our base to the ack+1
                        # If our ack is older than base, we received a duplicate ack. We now start suspecting packet loss.
                        # We increase the duplicate ack count and if it reaches 3, we perform fast retransmit.
                        elif packedSeqNum + 1 <= base: 
                            if lastACK == packedSeqNum:
                                dupACKcount += 1
                                
                                if dupACKcount == 3:
                                    base = packedSeqNum + 1
                                    dupACKcount = 0      
                                    ssthresh = max(congestionWindowSize // 2, 2)
                                    congestionWindowSize = ssthresh  # Reset congestion window      
                                    #print("Fast retransmit", base, end=" ")
                                #print("Duplicate ACK", end=" ")
                            else:
                                # If the last ack is not the same as the current ack, we reset the duplicate ack count
                                # there might be an out of order ack
                                dupACKcount = 0
                                #print("Out of order ACK", end=" ")
                        # Update last ack
                        lastACK = packedSeqNum
                        
                    with condB:
                        condB.notify_all()

                        #print(base)
                    with lockT:
                        with lockB:
                            # Reset timer
                            timer.cancel()
                            sampleRTT = time.time() - packedTime
                            timeoutInterval = calculateTimeoutInterval(sampleRTT)
                            timer = threading.Timer(timeoutInterval, MADPRetransmitter)
                            timer.start()
                    

                    # Adjust window size based on ACKs
                    with lockB:
                        if congestionWindowSize < ssthresh:
                            # Slow start phase
                            congestionWindowSize *= 2
                        else:
                            # Congestion avoidance phase
                            congestionWindowSize += 1 / congestionWindowSize
                else:
                    ##print("Corrupted ACK packet")
                    pass

            except KeyboardInterrupt:
                ##print("Exiting MADPAckHandler")
                break                             

    def MADPSender():
        """
        This function handles the sending of packets in the MADP protocol.

        It continuously sends packets until all chunks have been sent. It uses global variables
        to keep track of the current state of the sender.

        Globals:
        - chunkedData: A list containing the chunked data to be sent.
        - base: The base sequence number of the sliding window.
        - timer: The timer used for retransmission.
        - seqNum: The current sequence number.
        - congestionWindowSize: The congestion window size.
        - windowSize: The size of the sliding window.

        The function follows the following steps:
        1. Check if the current sequence number is equal to the total number of chunks. If so, break the loop.
        2. Get the current base sequence number.
        3. If the difference between the current sequence number and the base is less than the window size:
            - Get the file ID, chunk number, packet, flag, and is_large from the chunkedData list.
            - Pack the current time, sequence number, file ID, chunk number, flag, is_large, and packet.
            - Calculate the checksum of the packet.
            - Append the checksum, packed time, sequence number, file ID, chunk number, flag, is_large, and packet together.
            - Send the packet using the outgoingSocket.
            - If the current base is equal to the sequence number, cancel the timer and start a new one.
            - Increment the sequence number.
        4. If the difference between the current sequence number and the base is greater than or equal to the window size,
           wait for the base condition to be notified.
        5. Handle KeyboardInterrupt by breaking the loop.
        """
        global chunkedData, base, timer, seqNum, congestionWindowSize, windowSize, totalChunks
        while True:
            try:
                with lockD:
                    if seqNum == totalChunks: # All chunks are sent
                        break
                with lockB:
                    tempBase = base
                if seqNum - tempBase < windowSize:
                    with lockD:
                        file_id, chunk_num, packet, flag, is_large = chunkedData[seqNum]

                    # pack current time, seqNum, file_id, chunk_num, flag and is_large and packet
                    packedTime = struct.pack('!d', time.time())
                    packedSeqNum = struct.pack('!H', seqNum)
                    packedFileId = struct.pack('!H', file_id)
                    packedChunkNum = struct.pack('!H', chunk_num)
                    packedTotalChunks = struct.pack('!H', totalChunks)
                    packedFlag = struct.pack('!?', flag)
                    packedIsLarge = struct.pack('!?', is_large)
                    checkSum = hashlib.md5(packet).digest()
                    packet = checkSum + packedTime + packedSeqNum + packedFileId + packedChunkNum + packedTotalChunks + packedFlag + packedIsLarge + packet
                    outgoingSocket.sendto(packet, madpReceiverAddr)

                    if tempBase == seqNum:
                        with lockT:
                            timer.cancel()
                            timer = threading.Timer(timeoutInterval, MADPRetransmitter)
                            timer.start()

                    seqNum += 1                 

                else:
                    with condB:
                        condB.wait()

                #time.sleep(0.02)        

            except KeyboardInterrupt:
                ##print("Exiting MADPSender")
                break

    def MADPRetransmitter():
        """
        Retransmits packets that have not been acknowledged by the receiver.
        
        This function is responsible for retransmitting packets that have not been acknowledged by the receiver.
        It uses global variables to keep track of the current state of the transmission, including the base sequence number,
        the current sequence number, the timer, the congestion window size, and the slow start threshold.
        
        Globals:
            - base: The base sequence number of the transmission.
            - seqNum: The current sequence number.
            - timer: The timer used for retransmission.
            - congestionWindowSize: The size of the congestion window.
            - ssthresh: The slow start threshold.
        
        Returns:
            None
        """
         
        global base, seqNum, timer, congestionWindowSize, ssthresh, totalChunks
        
        with lockT:
            with lockB:
                if base == totalChunks:
                    return
                tempBase = base
            #print("Timeout for packet : ", tempBase, "interval is:", timeoutInterval)
            #print("Retransmitting packet: ", tempBase)
            for i in range(tempBase, seqNum):
                try:
                    with lockD:
                        file_id, chunk_num, packet, flag, is_large = chunkedData[i]
                    packedTime = struct.pack('!d', time.time())
                    packedSeqNum = struct.pack('!H', i)
                    packedFileId = struct.pack('!H', file_id)
                    packedChunkNum = struct.pack('!H', chunk_num)
                    packedTotalChunks = struct.pack('!H', totalChunks)
                    packedFlag = struct.pack('!?', flag)
                    packedIsLarge = struct.pack('!?', is_large)
                    checkSum = hashlib.md5(packet).digest()
                    packet = checkSum + packedTime + packedSeqNum + packedFileId + packedChunkNum + packedTotalChunks + packedFlag + packedIsLarge + packet
                    outgoingSocket.sendto(packet, madpReceiverAddr)

                    #time.sleep(0.02)
                except KeyboardInterrupt:
                    ##print("Exiting MADPRetransmitter")
                    break
            # Adjust congestion window and ssthresh on timeout
            ssthresh = max(congestionWindowSize // 2, 2)
            congestionWindowSize = 1
            timer.cancel()
            timer = threading.Timer(timeoutInterval, MADPRetransmitter)
            timer.start()


    def calculateTimeoutInterval(sampleRTT):
        global estimatedRTT, devRTT
        estimatedRTT = 0.875 * estimatedRTT + 0.125 * sampleRTT
        devRTT = 0.75 * devRTT + 0.25 * abs(sampleRTT - estimatedRTT)
        return min(estimatedRTT + 4 * devRTT, 2)
    
    ackThread = threading.Thread(target=MADPAckHandler)
    ackThread.daemon = True
    ackThread.start()

    timer = threading.Timer(timeoutInterval, MADPRetransmitter)

    MADPSender()

    ackThread.join()


                        
