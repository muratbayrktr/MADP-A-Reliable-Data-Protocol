import socket
import os
import struct
import time
from utils import FileReassembler

fileReassembler = FileReassembler()

def receiveFile(conn):
    global fileReassembler
    # Receive the file
    temp = bytearray()
    while True:
        data = conn.recv(1408)
        if not data:
            break
        temp += data


    # Reassemble the file
    offset = 0
    while offset < len(temp):
        header = temp[offset:offset + 8]
        packedFileId = struct.unpack('!H', header[0:2])[0]
        packedChunkNum = struct.unpack('!H', header[2:4])[0]
        packedChunkSize = struct.unpack('!H', header[4:6])[0]
        isLastChunk = struct.unpack('!?', header[6:7])[0]
        isLarge = struct.unpack('!?', header[7:8])[0]
        offset += 8
        packet = temp[offset:offset + packedChunkSize]
        offset += packedChunkSize
        # print(f"Received chunk {packedChunkNum} of file {packedFileId}, isLastChunk: {isLastChunk}, isLarge: {isLarge}")
        fileReassembler.add_chunk(packedFileId, packedChunkNum, packet, isLastChunk, isLarge)


def client():
    HOST = "172.17.0.3"  # The server's hostname or IP address
    PORT = 65432  # The port used by the server
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
        s.connect((HOST, PORT))
        print("Connected to the server...")
        totalTimetoReceive = 0
        
            
        # Receive the large and small object consecutively, measure the time
        startTime = time.time()
        
        receiveFile(s)

        endTime = time.time()
            
        timeTaken = endTime - startTime
        
        
        # Increment the total time
        totalTimetoReceive += timeTaken
        
        # Print the total time    
        print(f'Total time to receive: {totalTimetoReceive} seconds')

if __name__ == "__main__":
    client()




####  tcp çok hızlı olsun ama çok hızlı olmasın
    
## dosya dosya gönderme
    
## header koy yani dosya ismi, dosya boyutu, dosya tipi gibi bilgileri koy, sonra reconstruct et