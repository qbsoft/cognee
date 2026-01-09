from os import path
from io import BufferedReader
from typing import Union, BinaryIO
from tempfile import SpooledTemporaryFile

from cognee.modules.ingestion.exceptions import IngestionError
from .data_types import TextData, BinaryData, S3BinaryData


def classify(data: Union[str, BinaryIO], filename: str = None):
    if isinstance(data, str):
        return TextData(data)

    if isinstance(data, BufferedReader) or isinstance(data, SpooledTemporaryFile):
        # Prioritize provided filename over temporary file name
        # Use filename if provided, otherwise fallback to data.name
        actual_filename = filename if filename else str(data.name).split("/")[-1]
        return BinaryData(data, actual_filename)

    try:
        from s3fs import S3File
    except ImportError:
        S3File = None

    if S3File is not None:
        if isinstance(data, S3File):
            return S3BinaryData(s3_path=path.join("s3://", data.bucket, data.key), name=data.key)

    raise IngestionError(
        message=f"Type of data sent to classify(data: Union[str, BinaryIO) not supported or s3fs is not installed: {type(data)}"
    )
