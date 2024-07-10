from typing import BinaryIO, Iterator

from Cryptodome.Cipher import AES
from Cryptodome.Hash import SHA1
from Cryptodome.Protocol.KDF import PBKDF2


class SecureFileDecryptError(Exception):
    pass


class SecureFileCipher:
    def __init__(self, secret: str, salt: bytes):
        self._secret = secret
        self._salt = salt

    def _create_aes(self):
        NUM_ITERATIONS = 10000
        KEY_LEN = 32
        IV_LEN = 16

        derived_bytes = PBKDF2(
            self._secret,
            self._salt,
            KEY_LEN + IV_LEN,
            count=NUM_ITERATIONS,
            hmac_hash_module=SHA1,
        )

        key = derived_bytes[:KEY_LEN]
        iv = derived_bytes[KEY_LEN:]

        return AES.new(key, AES.MODE_CBC, iv)

    def _read_chunks(self, file_in: BinaryIO, chunk_size: int) -> Iterator[bytes]:
        buffer = b""

        while True:
            next_chunk = file_in.read(chunk_size)
            if not next_chunk:
                break

            num_wanted_bytes = chunk_size - len(buffer)
            buffer += next_chunk[:num_wanted_bytes]

            if len(buffer) == chunk_size:
                yield buffer
                buffer = next_chunk[num_wanted_bytes:]
            else:
                # We consumed all bytes
                assert num_wanted_bytes >= len(next_chunk)

        # Yield last chunk, if there are any bytes left
        if len(buffer):
            yield buffer

    def encrypt(
        self, file_in: BinaryIO, file_out: BinaryIO, chunk_size: int = 2**14
    ) -> None:
        block_size = AES.block_size
        if chunk_size % block_size != 0:
            raise ValueError(
                f"'{f'{chunk_size=}'.split('=')[0]}' must be a multiple of {block_size}"
            )

        aes = self._create_aes()

        last_to_enc_chunk: bytes = b""

        for next_to_enc_chunk in self._read_chunks(file_in, chunk_size):
            if last_to_enc_chunk:
                assert len(last_to_enc_chunk) % block_size == 0

                enc_bytes = aes.encrypt(last_to_enc_chunk)
                assert len(enc_bytes) == len(last_to_enc_chunk)

                file_out.write(enc_bytes)

            last_to_enc_chunk = next_to_enc_chunk

        # Apply PKCS#7 padding for AES

        pad_length = block_size - (len(last_to_enc_chunk) % block_size)
        assert pad_length > 0 and pad_length <= block_size

        padding = bytes([pad_length] * pad_length)
        last_to_enc_chunk += padding

        assert len(last_to_enc_chunk) % block_size == 0

        file_out.write(aes.encrypt(last_to_enc_chunk))

    def decrypt(
        self, file_in: BinaryIO, file_out: BinaryIO, chunk_size: int = 2**14
    ) -> None:
        block_size = AES.block_size
        if chunk_size % block_size != 0:
            raise ValueError(
                f"'{f'{chunk_size=}'.split('=')[0]}' must be a multiple of {block_size}"
            )

        aes = self._create_aes()

        last_dec_chunk: bytes = b""

        for enc_chunk in self._read_chunks(file_in, chunk_size):
            if len(enc_chunk) % block_size != 0:
                raise SecureFileDecryptError("Invalid file size")

            next_dec_chunk = aes.decrypt(enc_chunk)
            assert len(next_dec_chunk) == len(enc_chunk)

            if last_dec_chunk:
                file_out.write(last_dec_chunk)

            last_dec_chunk = next_dec_chunk

        if not last_dec_chunk:
            raise SecureFileDecryptError("Invalid file size")

        # Verify and remove PKCS#7 padding for AES

        pad_length: int = last_dec_chunk[-1]
        if not (pad_length > 0 and pad_length <= block_size):
            raise SecureFileDecryptError("Failed to decrypt")

        padding = bytes([pad_length] * pad_length)

        if last_dec_chunk[-pad_length:] != padding:
            raise SecureFileDecryptError("Invalid padding")

        last_dec_chunk = last_dec_chunk[:-pad_length]

        if last_dec_chunk:
            file_out.write(last_dec_chunk)
