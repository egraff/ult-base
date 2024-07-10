"""Python utility for encrypting and decrypting files, compatible with
AppVeyor's secure-file utility.
"""

import argparse
import base64
import secrets
import sys

from . import securefilecipher


def encrypt_file(file_path_in: str, secret: str, enc_file_path_out: str) -> None:
    salt_bytes = secrets.token_bytes(38)
    salt = base64.b64encode(salt_bytes).decode()
    cipher = securefilecipher.SecureFileCipher(secret, salt_bytes)

    with open(file_path_in, "rb") as file_in, open(
        enc_file_path_out, "w+b"
    ) as enc_file_out:
        cipher.encrypt(file_in, enc_file_out)

    print(f"Salt: {salt}")


def decrypt_file(
    enc_file_path_in: str, secret: str, salt: str, dec_file_path_out: str
) -> None:
    salt_bytes = base64.b64decode(salt)
    cipher = securefilecipher.SecureFileCipher(secret, salt_bytes)

    with open(enc_file_path_in, "rb") as enc_file_in, open(
        dec_file_path_out, "w+b"
    ) as dec_file_out:
        cipher.decrypt(enc_file_in, dec_file_out)


def run():
    parser = argparse.ArgumentParser(prefix_chars="+", add_help=False)
    subparsers = parser.add_subparsers(required=True, dest="cmd")

    _subparser_encrypt = subparsers.add_parser("-encrypt")
    _subparser_decrypt = subparsers.add_parser("-decrypt")

    parser_encrypt = argparse.ArgumentParser()
    parser_encrypt.add_argument(
        "-encrypt",
        metavar="<filename.ext>",
        dest="file",
        type=str,
        required=True,
    )
    parser_encrypt.add_argument(
        "-secret",
        metavar="<keyphrase>",
        dest="secret",
        type=str,
        required=True,
    )
    parser_encrypt.add_argument(
        "-out",
        metavar="<filename.ext.enc>",
        dest="out",
        type=str,
        required=True,
    )

    parser_decrypt = argparse.ArgumentParser()
    parser_decrypt.add_argument(
        "-decrypt",
        metavar="<filename.ext.enc>",
        dest="encrypted_file",
        type=str,
        required=True,
    )
    parser_decrypt.add_argument(
        "-secret",
        metavar="<keyphrase>",
        dest="secret",
        type=str,
        required=True,
    )
    parser_decrypt.add_argument(
        "-salt",
        metavar="<value>",
        dest="salt",
        type=str,
        required=True,
    )
    parser_decrypt.add_argument(
        "-out",
        metavar="<filename.ext>",
        dest="out",
        type=str,
        required=True,
    )

    args = parser.parse_args(sys.argv[1:2])

    if args.cmd == "-encrypt":
        enc_args = parser_encrypt.parse_args()
        encrypt_file(enc_args.file, enc_args.secret, enc_args.out)
    elif args.cmd == "-decrypt":
        dec_args = parser_decrypt.parse_args()
        decrypt_file(
            dec_args.encrypted_file, dec_args.secret, dec_args.salt, dec_args.out
        )
    else:
        assert False, "Unknown command"


if __name__ == "__main__":
    run()
