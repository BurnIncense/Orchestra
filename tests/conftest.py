import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pytest_plugins = []


def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark test as async")
    config.addinivalue_line("markers", "slow: mark test as slow")
    config.addinivalue_line("markers", "requires_gpu: mark test as requiring GPU")
    config.addinivalue_line("markers", "requires_model: mark test as requiring model")


@pytest.fixture(scope="session")
def config():
    from utils.config import load_config
    return load_config()


@pytest.fixture(scope="session")
def agent(config):
    try:
        from core.agent import OrchestraAgent
        return OrchestraAgent(config)
    except Exception as e:
        pytest.skip(f"无法创建 OrchestraAgent: {e}")


@pytest.fixture
def skip_if_no_gpu():
    try:
        import torch
        if not torch.cuda.is_available():
            pytest.skip("需要 GPU")
    except ImportError:
        pytest.skip("torch 未安装")
