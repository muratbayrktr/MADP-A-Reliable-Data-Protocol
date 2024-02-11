import socket
import os
import struct
import hashlib

DATA_FOLDER = "../app/objects"
PACKET_SIZE = 1400


def readData():
    data = {}
    for i in range(10):
        with open(DATA_FOLDER + f'/small-{i}.obj', 'rb') as f:
            data[f'small-{i}.obj'] = f.read()
    for i in range(10):
        with open(DATA_FOLDER + f'/large-{i}.obj', 'rb') as f:
            data[f'large-{i}.obj'] = f.read()        
    return data

def chunks(data):
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
                # #print(f"Chunk {chunk_num} of file {size}-{j}.obj is {len(chunk)} bytes long")
                tempchunked.append((file_id, chunk_num, chunk, 0, is_large)) # 0 means not last chunk
            tempchunked[-1] = (file_id, chunk_num, chunk, 1, is_large)
            #print(tempchunked[-1])
            chunked += tempchunked
            #print(f"File {size}-{j}.obj has {len(tempchunked)} chunks. Total chunks: {len(chunked)}")
            # data[f'{size}-{j}.obj'] = chunked
    return chunked, len(chunked)   


def sendFile( conn):
    data = readData()
    allchunks, total_chunks = interleaved_chunks(data) 
    print(total_chunks)
    for chunk in allchunks:
         packedFileId = struct.pack('!H', chunk[0])  # 2 bytes
         packedChunkNum = struct.pack('!H', chunk[1]) # 2 bytes
         packedChunkSize = struct.pack('!H', len(chunk[2])) # 2 bytes
         packedFlag = struct.pack('!?', chunk[3])  # 1 byte
         packedIsLarge = struct.pack('!?', chunk[4]) # 1 byte
         packet = chunk[2]
         packet = packedFileId + packedChunkNum + packedChunkSize + packedFlag + packedIsLarge + packet
         #print(f"Sending chunk {chunk[1]} of file {chunk[0]}, isLastChunk: {chunk[3]}, isLarge: {chunk[4]}")
         conn.send(packet)

# rest of the server code remains the same


def server():
    HOST = "172.17.0.3"  # Server instance IP address
    PORT = 65432  # Port to listen on (non-privileged ports are > 1023)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
        s.bind((HOST, PORT))
        s.listen()
        print("Server is waiting for client to connect...")

        conn, addr = s.accept()
        with conn:

            # We arranged the connection
            print(f"Client {addr} connected")
            
            sendFile(conn)

            print("All objects are sent.")    
                
if __name__ == "__main__":
    server()


