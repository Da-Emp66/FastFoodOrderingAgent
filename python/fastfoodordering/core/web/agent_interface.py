import abc
from typing import AsyncGenerator, Literal, Union

from pydantic import BaseModel

from core.utils import ToolReport

class Plan(BaseModel):
    plan: str

IterativeTaskResult = Union[Plan, ToolReport, Literal['<|COMPLETED_OVERALL_TASK|>']]

class Agent(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def iterate_task(self) -> AsyncGenerator[IterativeTaskResult, IterativeTaskResult]:
        raise NotImplementedError()
    