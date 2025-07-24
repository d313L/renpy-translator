import os
import struct
import zlib

MAGIC = b"RPA-3.0"

def extract_rpa(archive_path, output_dir):
    with open(archive_path, "rb") as f:
        if f.read(7) != MAGIC:
            raise ValueError("Not a supported RPA-3.0 file")

        index_offset = struct.unpack("<Q", f.read(8))[0]
        f.seek(index_offset)
        index = eval(f.read().decode("utf-8"), {"__builtins__": {}})

        for path, info in index.items():
            out_path = os.path.join(output_dir, path)
            os.makedirs(os.path.dirname(out_path), exist_ok=True)

            f.seek(info[0])
            data = f.read(info[1])
            if info[2] == "z":
                data = zlib.decompress(data)
            with open(out_path, "wb") as out_file:
                out_file.write(data)

        return len(index)
