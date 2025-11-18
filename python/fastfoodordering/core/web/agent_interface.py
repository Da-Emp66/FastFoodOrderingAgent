import abc
from typing import AsyncGenerator, Literal, Optional, Union

from pydantic import BaseModel

from core.utils import ToolCaller, ToolReport

class Plan(BaseModel):
    plan: str

IterativeTaskResult = Union[Plan, ToolReport, Literal['<|COMPLETED_OVERALL_TASK|>']]

class Agent(metaclass=abc.ABCMeta):
    tool_caller: Optional[ToolCaller] = None
    @abc.abstractmethod
    async def iterate_task(self) -> AsyncGenerator[IterativeTaskResult, IterativeTaskResult]:
        raise NotImplementedError()
    