from pathlib import Path

from multilspy import SyncLanguageServer
from multilspy.multilspy_config import MultilspyConfig
from multilspy.multilspy_logger import MultilspyLogger

config = MultilspyConfig.from_dict(
    {"code_language": "solidity"}
)  # Also supports "python", "rust", "csharp", "typescript", "javascript", "go", "dart", "ruby", "solidity"
logger = MultilspyLogger(True)
repository_root = Path(__file__).resolve().parent
lsp = SyncLanguageServer.create(config, logger, str(repository_root))
with lsp.start_server():
    # Test Solidity language server with a sample contract
    result = lsp.request_definition(
        "tests/contracts/SampleContract.sol",  # Filename of location where request is being made
        16,  # line number of symbol for which request is being made
        13  # column number of symbol for which request is being made
    )
    print(result)
    result = lsp.request_definition(
        "tests/contracts/SampleContract.sol",  # Filename of location where request is being made
        16,  # line number of symbol for which request is being made
        13  # column number of symbol for which request is being made
    )
    print(result)
    # You can also test other requests:
    # result = lsp.request_definition("contracts/SampleContract.sol", 10, 15)
    # result = lsp.request_completion("contracts/SampleContract.sol", 20, 10)
