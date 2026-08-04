from dataclasses import dataclass

@dataclass(frozen=True)
class ExecutionContext:
    execution_mode: str  # "PAPER" or "LIVE"
    deployment_id: str
    strategy_id: str
    version: str

    @property
    def is_paper(self) -> bool:
        return self.execution_mode.upper() == "PAPER"
