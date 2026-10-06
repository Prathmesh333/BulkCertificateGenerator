import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Settings:
    database_url: str = "sqlite:///./storage/certificates.db"
    storage_dir: Path = Path("storage")
    template_dir: Path = Path(__file__).parent / "templates" / "default"
    max_recipients: int = 1000
    max_attempts: int = 3
    poll_seconds: float = 1

    @classmethod
    def from_env(cls):
        return cls(
            database_url=os.getenv("DATABASE_URL", cls.database_url),
            storage_dir=Path(os.getenv("STORAGE_DIR", "storage")),
            template_dir=Path(os.getenv("TEMPLATE_DIR", str(cls.template_dir))),
            max_recipients=int(os.getenv("MAX_RECIPIENTS_PER_JOB", "1000")),
            max_attempts=int(os.getenv("MAX_PROCESSING_ATTEMPTS", "3")),
            poll_seconds=float(os.getenv("WORKER_POLL_INTERVAL_SECONDS", "1")),
        )
