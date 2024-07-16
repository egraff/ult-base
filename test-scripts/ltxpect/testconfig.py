from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class TestConfig:
    test_base_dir: str
    proto_dir: str
    num_concurrent_processes: int = 8
