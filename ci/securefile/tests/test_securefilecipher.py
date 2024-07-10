import base64
import io
import random
import unittest

from ..securefilecipher import SecureFileCipher


class FakeStreamLikeReadIO:
    def __init__(self, read_bytes: bytes):
        self._read_bytes = read_bytes

    def read(self, read_len):
        assert read_len > 0

        if not self._read_bytes:
            return b""

        num_bytes = min(random.randint(1, 10), read_len)

        next_result = self._read_bytes[:num_bytes]
        self._read_bytes = self._read_bytes[num_bytes:]

        return next_result


class SecureFileCipherTests(unittest.TestCase):
    PASSWORD = "supersecretpassword"
    SALT = base64.b64decode("iW+1djm1NmJ2yFYdetG5YUHu5aLeCcCRCo+KEM+I6LssqwO1PME=")

    LOREM_RAW = b"\n".join(
        [
            b"Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor",
            b"incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis",
            b"nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.",
            b"Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore",
            b"eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt",
            b"in culpa qui officia deserunt mollit anim id est laborum.",
            b"",
        ]
    )
    LOREM_ENC = "UudZdcJdSOCyDYH++NqWbw7EhLHpRz/LrwUAXbJyGqO9EZ6oSXQvQ4mZYHWtvQpTFn57ZOhGRAF29XFGcGRiH2+gohbzZRgdr9UQrc7H8EmW9MdzmX4hgq8vaR4OeKyD3DUvDxPve703rZKeI8xEgiLNePg6xllThbhoYXbmeLZ8WaLZlOur9t1eP/U8fxfHo04XvbGStTqxkRWPQNh7e9DTQg2nJnVMLYVq0N7kHCSPnYuhkJqJzJt0GJH8VEyDiNdMkZiokaCbOVZp+Km9FUSswxFKv//x8rz4+u6szF955blf1CxAcWtIpj7HMYLs9QVQ0XykJkOd6tMvQVPyXb4b4PwPVkUDUVSgPuYbicALP9qkzF0UdAB/tCn3dTA/u2LLU5nUh9/Eirwbjy0BQ51WmtwUL86l5ymreGH5VipZye8sfwuLXxBKLh1Rvn/I295kI4VwdFtAjc2R+BEumiWoQOw/CP6AQ76scIG72qq7WEY191jGSpPf8R9SQ+0ZLR1y3ZkrVfj/pAcfMYCqCaMHZjKSpwFCe36z5DIMx3Lb5+qZkilWtqMe/PnQSpBr09+gGzOjDlGisgVMO0Rw3Q=="

    def test_encrypt_with_default_chunk_size(self):
        # Arrange

        cipher = SecureFileCipher(self.PASSWORD, self.SALT)

        file_in = io.BytesIO(self.LOREM_RAW)
        file_out = io.BytesIO()

        # Act

        cipher.encrypt(file_in, file_out)

        # Assert

        self.assertEqual(file_out.getvalue(), base64.b64decode(self.LOREM_ENC))

    def test_encrypt_with_chunk_size_equal_to_block_size(self):
        # Arrange

        cipher = SecureFileCipher(self.PASSWORD, self.SALT)

        file_in = io.BytesIO(self.LOREM_RAW)
        file_out = io.BytesIO()

        # Act

        cipher.encrypt(file_in, file_out, 16)

        # Assert

        self.assertEqual(file_out.getvalue(), base64.b64decode(self.LOREM_ENC))

    def test_encrypt_with_stream_like_input(self):
        # Arrange

        cipher = SecureFileCipher(self.PASSWORD, self.SALT)

        file_in = FakeStreamLikeReadIO(self.LOREM_RAW)
        file_out = io.BytesIO()

        # Act

        cipher.encrypt(file_in, file_out)

        # Assert

        self.assertEqual(file_out.getvalue(), base64.b64decode(self.LOREM_ENC))

    def test_encrypt_with_stream_like_input_and_small_chunk_size(self):
        # Arrange

        cipher = SecureFileCipher(self.PASSWORD, self.SALT)

        file_in = FakeStreamLikeReadIO(self.LOREM_RAW)
        file_out = io.BytesIO()

        # Act

        cipher.encrypt(file_in, file_out, 16)

        # Assert

        self.assertEqual(file_out.getvalue(), base64.b64decode(self.LOREM_ENC))

    def test_decrypt_with_default_chunk_size(self):
        # Arrange

        cipher = SecureFileCipher(self.PASSWORD, self.SALT)

        file_in = io.BytesIO(base64.b64decode(self.LOREM_ENC))
        file_out = io.BytesIO()

        # Act

        cipher.decrypt(file_in, file_out)

        # Assert

        self.assertEqual(file_out.getvalue(), self.LOREM_RAW)

    def test_decrypt_with_chunk_size_equal_to_block_size(self):
        # Arrange

        cipher = SecureFileCipher(self.PASSWORD, self.SALT)

        file_in = io.BytesIO(base64.b64decode(self.LOREM_ENC))
        file_out = io.BytesIO()

        # Act

        cipher.decrypt(file_in, file_out, 16)

        # Assert

        self.assertEqual(file_out.getvalue(), self.LOREM_RAW)

    def test_decrypt_with_stream_like_input(self):
        # Arrange

        cipher = SecureFileCipher(self.PASSWORD, self.SALT)

        file_in = FakeStreamLikeReadIO(base64.b64decode(self.LOREM_ENC))
        file_out = io.BytesIO()

        # Act

        cipher.decrypt(file_in, file_out)

        # Assert

        self.assertEqual(file_out.getvalue(), self.LOREM_RAW)

    def test_decrypt_with_stream_like_input_and_small_chunk_size(self):
        # Arrange

        cipher = SecureFileCipher(self.PASSWORD, self.SALT)

        file_in = FakeStreamLikeReadIO(base64.b64decode(self.LOREM_ENC))
        file_out = io.BytesIO()

        # Act

        cipher.decrypt(file_in, file_out, 16)

        # Assert

        self.assertEqual(file_out.getvalue(), self.LOREM_RAW)
