from pathlib import Path

from multilspy import SyncLanguageServer
from multilspy.multilspy_config import MultilspyConfig
from multilspy.multilspy_logger import MultilspyLogger


def main() -> None:
    config = MultilspyConfig.from_dict({"code_language": "java"})
    logger = MultilspyLogger(True)
    repository_root = "/Users/mac/repo/deepwiki-cli/bench/java-polymorphism-execute/"
    # repository_root = "/Users/mac/repo/deepwiki-cli/bench/java-polymorphism-execute"

    lsp = SyncLanguageServer.create(config, logger, str(repository_root))
    with lsp.start_server():
        results = lsp.request_implementations(
            'src/main/java/com/example/polymorphism/AbstractExecutor.java',
            13,
            18,
        )
        for result in results:
            print(result)


if __name__ == "__main__":
    main()
