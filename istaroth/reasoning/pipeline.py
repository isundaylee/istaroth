"""Reasoning pipeline with LangChain agents."""

import logging
import time

from langchain import agents, prompts
from langchain.agents import AgentExecutor
from langchain_core import language_models, tools
from langchain_core.prompts import MessagesPlaceholder

from istaroth import langsmith_utils, llm_manager
from istaroth.agd import localization
from istaroth.rag import document_store
from istaroth.reasoning import prompts as reasoning_prompts
from istaroth.reasoning import types

logger = logging.getLogger(__name__)


class ReasoningPipeline:
    """Multi-step reasoning pipeline with tool use."""

    def __init__(
        self,
        llm: language_models.BaseLanguageModel,
        document_store: document_store.DocumentStore,
        language: localization.Language = localization.Language.ENG,
    ):
        """Initialize pipeline with LLM, document store and language."""
        self._llm = llm
        self._document_store = document_store
        self._language = language

        # Tool registry - stores LangChain tools
        self._tools: list[tools.BaseTool] = []

        # Agent executor (will be created when tools are registered)
        self._agent_executor: AgentExecutor

        # Get language-specific prompts
        self._prompt_set = reasoning_prompts.get_reasoning_prompts(language)

        # Initialize with empty agent executor (will be created when tools are registered)
        self._agent_executor = self._create_agent_executor(
            llm=self._llm, tools=self._tools, prompt_set=self._prompt_set
        )

    def register_tool(self, tool: tools.BaseTool) -> None:
        """Register a tool for reasoning."""
        self._tools.append(tool)
        logger.info("Registered tool: %s", tool.name)

        # Recreate agent executor with updated tools
        self._agent_executor = self._create_agent_executor(
            llm=self._llm, tools=self._tools, prompt_set=self._prompt_set
        )

    @staticmethod
    def _create_agent_executor(
        llm: language_models.BaseLanguageModel,
        tools: list[tools.BaseTool],
        prompt_set: reasoning_prompts.ReasoningPrompts,
    ) -> AgentExecutor:
        """Create agent executor with provided tools."""
        # Create agent with tools
        agent = agents.create_tool_calling_agent(
            llm=llm,
            tools=tools,
            prompt=prompts.ChatPromptTemplate.from_messages(
                [
                    ("system", prompt_set.system_prompt),
                    ("user", "{input}"),
                    MessagesPlaceholder(variable_name="agent_scratchpad"),
                ]
            ),
        )

        # Create executor
        return AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            max_iterations=5,
            return_intermediate_steps=True,
        )

    @langsmith_utils.traceable(name="reasoning_pipeline")
    def reason(
        self,
        request: types.ReasoningRequest,
    ) -> types.ReasoningResponse:
        """Execute reasoning with optional tool use."""
        reasoning_steps = []

        # Prepare input - just the question, context comes from tools
        input_text = request.question

        # Execute with agent
        result = self._agent_executor.invoke(
            {"input": input_text}, config={"max_iterations": request.max_steps}
        )

        # Process intermediate steps into reasoning steps
        for action, observation in result.get("intermediate_steps", []):
            # Add tool call step
            reasoning_steps.append(
                types.ReasoningStep(
                    step_type="tool_call",
                    content=f"Called {action.tool} with arguments: {action.tool_input}",
                    timestamp=time.time(),
                )
            )

            # Add tool result step
            reasoning_steps.append(
                types.ReasoningStep(
                    step_type="tool_result",
                    content=str(observation),
                    timestamp=time.time(),
                )
            )

        final_answer = result.get("output", "")

        # Add conclusion step
        reasoning_steps.append(
            types.ReasoningStep(
                step_type="conclusion",
                content=final_answer,
                timestamp=time.time(),
            )
        )

        return types.ReasoningResponse(
            question=request.question,
            answer=final_answer,
            reasoning_steps=reasoning_steps,
            model=llm_manager.get_model_name(self._llm),
        )
