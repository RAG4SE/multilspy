from pathlib import Path

from multilspy import SyncLanguageServer
from multilspy.multilspy_config import MultilspyConfig
from multilspy.multilspy_logger import MultilspyLogger


def main() -> None:
    config = MultilspyConfig.from_dict({"code_language": "java"})
    logger = MultilspyLogger(True)
    repository_root = "/Users/mac/repo/icardcenter"
    # repository_root = "/Users/mac/repo/deepwiki-cli/bench/java-polymorphism-execute"

    lsp = SyncLanguageServer.create(config, logger, str(repository_root))
    with lsp.start_server():
        result = lsp.request_definition(
            '/Users/mac/repo/icardcenter/app/biz/service-impl/src/main/java/com/ipay/icardcenter/service/template/ServiceExecuteTemplate.java',
            63,
            21,
        )
        # result = lsp.request_definition(
        #     'src/main/java/com/example/polymorphism/Main.java',
        #     144,
        #     12,
        # )
        print(result)


if __name__ == "__main__":
    main()
