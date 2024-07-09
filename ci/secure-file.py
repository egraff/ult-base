"""Python utility for decrypting encrypted files, compatible with the
encryption performed by AppVeyor's secure-file utility.
"""

import argparse
import base64
from typing import BinaryIO

from Crypto.Cipher import AES
from Crypto.Hash import SHA1
from Crypto.Protocol.KDF import PBKDF2


def decrypt(enc_file_in: BinaryIO, dec_file_out: BinaryIO, secret: str, salt: str):
    derived_bytes = PBKDF2(
        secret, base64.b64decode(salt), 48, count=10000, hmac_hash_module=SHA1
    )

    key = derived_bytes[:32]
    iv = derived_bytes[32:]

    aes = AES.new(key, AES.MODE_CBC, iv)

    last_dec_chunk: bytes = b""

    while True:
        enc_bytes = enc_file_in.read(aes.block_size * 1024)
        if not enc_bytes:
            break

        assert len(enc_bytes) % aes.block_size == 0
        next_dec_chunk = aes.decrypt(enc_bytes)
        if not next_dec_chunk:
            break

        if last_dec_chunk:
            dec_file_out.write(last_dec_chunk)

        last_dec_chunk = next_dec_chunk

    if last_dec_chunk:
        pad_length: int = last_dec_chunk[-1]
        assert pad_length > 0 and pad_length <= aes.block_size

        padding = bytes([pad_length] * pad_length)
        assert last_dec_chunk[-pad_length:] == padding

        last_dec_chunk = last_dec_chunk[:-pad_length]

        if last_dec_chunk:
            dec_file_out.write(last_dec_chunk)


def decrypt_file(
    enc_file_path_in: str, secret: str, salt: str, dec_file_path_out: str
) -> None:
    with open(enc_file_path_in, "rb") as enc_file_in, open(
        dec_file_path_out, "w+b"
    ) as dec_file_out:
        decrypt(enc_file_in, dec_file_out, secret, salt)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-decrypt",
        dest="decrypt",
        type=str,
        required=True,
    )
    parser.add_argument(
        "-secret",
        dest="secret",
        type=str,
        required=True,
    )
    parser.add_argument(
        "-salt",
        dest="salt",
        type=str,
        required=True,
    )
    parser.add_argument(
        "-out",
        dest="out",
        type=str,
        required=True,
    )

    args = parser.parse_args()

    decrypt_file(args.decrypt, args.secret, args.salt, args.out)
