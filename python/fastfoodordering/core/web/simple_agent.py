from typing import Any, AsyncGenerator, Union
from browser_use import Agent, Browser, ChatBrowserUse
from pydantic import BaseModel

from core.utils import from_config
from core.web.agent_interface import IterativeTaskResult

class SimpleBrowserAgentConfiguration(BaseModel):
    task_prompt_template: str

class SimpleBrowserAgent:
    def __init__(self, configuration: Union[SimpleBrowserAgentConfiguration, Any]):
        self.configuration: SimpleBrowserAgentConfiguration = from_config(configuration, SimpleBrowserAgentConfiguration)
        self.browser = Browser()
        self.llm = ChatBrowserUse()

    async def iterate_task(self) -> AsyncGenerator[IterativeTaskResult, IterativeTaskResult]:
        import shared
        overall_goal = shared.this_session.current_spec.objective_spec.objective
        print(f"Overall goal is currently: {overall_goal}", flush=True)

        task = self.configuration.task_prompt_template.replace("{overall_goal}")
        self.agent = Agent(
            task=task,
            llm=self.llm,
            browser=self.browser,
        )
        yield await self.agent.run()
