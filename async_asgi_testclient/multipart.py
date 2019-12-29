from typing import Dict
from typing import Tuple
from typing import Union

import binascii
import os


def encode_multipart_formdata(
    fields: Dict[str, Union[str, Tuple]]
) -> Tuple[bytes, str]:
    # Based on https://julien.danjou.info/handling-multipart-form-data-python/
    boundary = binascii.hexlify(os.urandom(16)).decode("ascii")

    body = (
        "".join(
            build_part(boundary, field_name, file_tuple)
            for field_name, file_tuple in fields.items()
        )
        + f"--{boundary}--\r\n"
    )

    content_type = f"multipart/form-data; boundary={boundary}"

    return body.encode("ascii"), content_type


def build_part(boundary: str, field_name: str, file_tuple: Union[str, Tuple]) -> str:
    """
    file_tuple:
        - 'string value'
        - (fileobj,)
        - ('filename', fileobj)
        - ('filename', fileobj, 'content_type')
    """
    value = ""
    filename = ""
    content_type = ""

    if isinstance(file_tuple, str):
        value = file_tuple
    else:
        if len(file_tuple) == 1:
            file_ = file_tuple[0]
        elif len(file_tuple) == 2:
            filename, file_ = file_tuple
        elif len(file_tuple) == 3:
            filename, file_, content_type = file_tuple
        value = file_.read()

    part = f'--{boundary}\r\nContent-Disposition: form-data; name="{field_name}"'
    if filename:
        part += f'; filename="{filename}"'

    if content_type:
        part += f"\r\nContent-Type: {content_type}"

    if isinstance(value, bytes):
        value = value.decode("ascii")

    return part + "\r\n\r\n" + value + "\r\n"
