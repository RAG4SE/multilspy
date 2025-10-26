from pathlib import Path

from multilspy import SyncLanguageServer
from multilspy.multilspy_config import MultilspyConfig
from multilspy.multilspy_logger import MultilspyLogger


def main() -> None:
    config = MultilspyConfig.from_dict({"code_language": "java"})
    logger = MultilspyLogger(True)
    repository_root = Path(__file__).resolve().parent / "tests" / "java_sample"

    lsp = SyncLanguageServer.create(config, logger, str(repository_root))
    with lsp.start_server():
        result = lsp.request_definition(
            "src/main/java/com/example/App.java",
            5,
            27,
        )
        print(result[0])
    with lsp.start_server():
        result = lsp.request_definition(
            "src/main/java/com/example/App.java",
            5,
            27,
        )
        print(result[0])


if __name__ == "__main__":
    main()
