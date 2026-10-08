"""Persistent object storage with a local working-file cache."""
from pathlib import Path


class Storage:
    def __init__(self, settings):
        self.root = settings.storage_dir
        self.bucket = settings.s3_bucket
        self.client = None
        if self.bucket:
            import boto3
            from botocore.config import Config
            self.client = boto3.client("s3", endpoint_url=settings.s3_endpoint,
                                       config=Config(signature_version="s3v4", retries={"max_attempts": 2},
                                                     connect_timeout=10, read_timeout=30))

    def key(self, path):
        return Path(path).relative_to(self.root).as_posix()

    def save(self, path):
        if self.client:
            self.client.upload_file(str(path), self.bucket, self.key(path))

    def load(self, path):
        path = Path(path)
        if self.client:
            from botocore.exceptions import ClientError
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                self.client.download_file(self.bucket, self.key(path), str(path))
            except ClientError as exc:
                if exc.response["Error"]["Code"] in {"404", "NoSuchKey", "NotFound"}:
                    return False
                raise
        return path.is_file()

    def url(self, path, filename=None):
        params = {"Bucket": self.bucket, "Key": self.key(path)}
        if filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
        return self.client.generate_presigned_url("get_object", Params=params, ExpiresIn=600)
