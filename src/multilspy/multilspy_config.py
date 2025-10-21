"""
Configuration parameters for Multilspy.
"""

from enum import Enum
from dataclasses import dataclass

class Language(str, Enum):
    """
    Possible languages with Multilspy.
    """

    CSHARP = "csharp"
    PYTHON = "python"
    RUST = "rust"
    JAVA = "java"
    KOTLIN = "kotlin"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    GO = "go"
    RUBY = "ruby"
    DART = "dart"
    CPP = "cpp"
    SOLIDITY = "solidity"

    def __str__(self) -> str:
        return self.value

@dataclass
class MultilspyConfig:
    """
    Configuration parameters
    """
    code_language: Language
    trace_lsp_communication: bool = False
    start_independent_lsp_process: bool = True

    @classmethod
    def from_dict(cls, env: dict):
        """
        Create a MultilspyConfig instance from a dictionary
        """
        import inspect

        kwargs = {}
        signature = inspect.signature(cls).parameters

        for key in signature:
            if key not in env:
                continue
            value = env[key]
            if key == "code_language":
                if isinstance(value, str):
                    try:
                        value = Language(value.lower())
                    except ValueError as exc:
                        raise ValueError(f"Unsupported language '{value}'") from exc
                elif not isinstance(value, Language):
                    raise TypeError(f"code_language must be a str or Language enum, received {type(value)}")
            kwargs[key] = value

        return cls(**kwargs)
