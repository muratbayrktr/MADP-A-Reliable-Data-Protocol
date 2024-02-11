import os 
import hashlib
import struct
# Read data from file
def read_objects_from_file(path, size:str, file_id:int):
    """
    Read data from file

    size: Either small or large
    file_id: an integer value.

    Destination is path + size + "-" + file_id + ".obj"
    """
    file_path = path + size + "-" + str(file_id) + ".obj"
    chsum_path = file_path + ".md5"
    return file_path, chsum_path
    # with open(file_path, "rb") as f:
    #     data = f.read()
    #     size = len(data)
    # return data, size
    

class FileReassembler:
    def __init__(self):
        self.files = {}  # Dictionary to hold file data

    def add_chunk(self, file_id, chunk_number, data, flags, is_large):
        """
        Add a chunk to the file assembly.

        Args:
            file_id (int): Identifier for the file.
            chunk_number (int): Sequence number of the chunk in the file.
            data (bytes): The actual data chunk.
        """
        file_id = f"l{file_id}" if is_large else f"s{file_id}"
        if file_id not in self.files:
            self.files[file_id] = {}

        self.files[file_id][chunk_number] = data
        # print(f"Added chunk {chunk_number} of file {file_id}")
        # Check if file assembly is complete
        if flags == 1 and self.is_file_complete(file_id):
            file = self.assemble_file(file_id)
            # Write the file to disk
            with open(f"reconstructed_{file_id}.obj", "wb") as f:
                f.write(file)
            # Remove the file from the dictionary
            del self.files[file_id]

        return None

    def is_file_complete(self, file_id):
        """
        Check if all chunks of a file have been received.

        Args:
            file_id (int): Identifier for the file.

        Returns:
            bool: True if the file is complete, False otherwise.
        """
        if file_id not in self.files:
            return False

        total_chunks = max(self.files[file_id].keys())
        # Sort the keys
        return all(chunk in self.files[file_id] for chunk in range(1, total_chunks + 1))

        

    def assemble_file(self, file_id):
        """
        Assemble the complete file from its chunks.

        Args:
            file_id (int): Identifier for the file.

        Returns:
            bytes: The assembled file data.
        """
        file_data = [self.files[file_id][chunk_number] for chunk_number in sorted(self.files[file_id])]
        return b"".join(file_data)
    

class PreparePacket:
    @classmethod
    def calculate_checksum(cls, data, header_size=1024, tail_size=1024):
        """
        Calculate the checksum on the header and tail of the data.

        Args:
            data (bytes): The data for which to calculate the checksum.
            header_size (int): Size of the header portion to include in checksum.
            tail_size (int): Size of the tail portion to include in checksum.

        Returns:
            bytes: The checksum.
        """
        header = data[:header_size]
        tail = data[-tail_size:]
        checksum_data = header + tail
        return hashlib.md5(checksum_data).digest()
    
    @classmethod
    def verify_checksum(cls, data, received_checksum):
        """
        Verifies the checksum of the data.

        Args:
            data (bytes): The data to verify.
            received_checksum (bytes): The checksum received in the header.

        Returns:
            bool: True if the checksum is correct, False otherwise.
        """
        calculated_checksum = cls.calculate_checksum(data)
        return calculated_checksum == received_checksum
    
    @classmethod
    def make_header(cls, seq_num, ack_num, flags, is_large, file_id, chunk_number, payload_length, payload):
        """
        Construct a packet header including file_id and chunk_number.

        Args:
            seq_num (int): Sequence number.
            ack_num (int): Acknowledgment number.
            flags (int): Control flags.
            file_id (int): Unique identifier for the file.
            chunk_number (int): The sequence number of the chunk within the file.
            payload_length (int): Length of the payload.
            payload (bytes): The payload data.

        Returns:
            bytes: The packed header.
        """
        checksum = cls.calculate_checksum(payload)
        header_format = 'IIIIBBH'  # Updated format
        header = struct.pack(header_format, seq_num, ack_num, file_id, chunk_number, flags, is_large, payload_length) + checksum
        return header

    @classmethod
    def parse_header(cls, header):
        """
        Parse a packet header.

        Args:
            header (bytes): The packed header.

        Returns:
            tuple: Unpacked header values.
        """
        header_format = 'IIIIBBH'
        # Last 16 bytes is the checksum
        checksum = header[-16:]
        seq_num, ack_num, file_id, chunk_number, flags, is_large, payload_length = struct.unpack(header_format, header[:20])
        return  seq_num, ack_num, file_id, chunk_number, flags, is_large, payload_length, checksum