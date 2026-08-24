"""Small OpenAI adapter used by the LangGraph nodes."""

from dataclasses import dataclass

from openai import OpenAI
from pydantic import BaseModel, Field

from app.config import Settings


MAX_WEB_SEARCH_CALLS = 6


class ResearchPlan(BaseModel):
    """Structured output returned by the planning call."""

    tasks: list[str] = Field(min_length=3, max_length=6)


class ReportReview(BaseModel):
    """Structured output returned by the review call."""

    score: int = Field(ge=0, le=100)
    comment: str = Field(min_length=1)


class ResearchEvaluation(BaseModel):
    """Structured assessment of whether the collected evidence is sufficient."""

    score: int = Field(ge=0, le=100)
    comment: str = Field(min_length=1)


@dataclass(frozen=True)
class ResearchResult:
    """Research notes and the source URLs used to produce them."""

    content: str
    sources: list[str]


class OpenAIResearchService:
    """Provide the LLM operations needed by the research graph."""

    def __init__(
        self,
        client=None,
        model: str | None = None,
        search_model: str | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._search_model = search_model

    def create_plan(self, topic: str) -> list[str]:
        """Ask the model to split a topic into concrete research tasks."""

        client, model = self._get_client_and_model()
        response = client.responses.parse(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "你是一名研究规划专家。请把研究主题拆成 3 到 6 个具体、"
                        "互不重复且适合后续检索的研究任务。"
                    ),
                },
                {"role": "user", "content": f"研究主题：{topic}"},
            ],
            text_format=ResearchPlan,
        )

        plan = response.output_parsed
        if plan is None:
            raise RuntimeError("Planner 没有返回可解析的研究计划。")

        return plan.tasks

    def research(
        self,
        topic: str,
        tasks: list[str],
        existing_research: str = "",
        evaluation_comment: str = "",
    ) -> ResearchResult:
        """Search the web and summarize findings for the research plan."""

        client, model = self._get_client_and_model(for_search=True)
        task_list = "\n".join(
            f"{index}. {task}" for index, task in enumerate(tasks, start=1)
        )
        follow_up_request = ""
        if evaluation_comment:
            follow_up_request = (
                f"\n\n已有研究资料：\n{existing_research}\n\n"
                f"资料评估指出的缺口：\n{evaluation_comment}\n\n"
                "请针对缺口做补充搜索，避免重复已有资料。"
            )
        response = client.responses.create(
            model=model,
            tools=[{"type": "web_search"}],
            tool_choice="required",
            max_tool_calls=MAX_WEB_SEARCH_CALLS,
            include=["web_search_call.action.sources"],
            input=[
                {
                    "role": "system",
                    "content": (
                        "你是一名事实核查严格的研究员。必须使用网页搜索完成每个"
                        "研究任务，优先选择官方、一手和近期来源。用中文总结，"
                        "关键事实附 Markdown 链接，不确定的信息要明确说明。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"研究主题：{topic}\n\n研究任务：\n{task_list}"
                        f"{follow_up_request}"
                    ),
                },
            ],
        )

        content = (response.output_text or "").strip()
        if not content:
            raise RuntimeError("Researcher 没有返回研究资料。")

        sources = self._extract_source_urls(response)
        if not sources:
            raise RuntimeError("Researcher 没有返回可验证的网页来源。")

        return ResearchResult(content=content, sources=sources)

    def evaluate_research(
        self,
        topic: str,
        tasks: list[str],
        research_content: str,
        sources: list[str],
    ) -> ResearchEvaluation:
        """Judge whether the evidence is sufficient to write the report."""

        client, model = self._get_client_and_model()
        task_list = "\n".join(f"- {task}" for task in tasks)
        source_list = "\n".join(f"- {source}" for source in sources)
        response = client.responses.parse(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "你是一名研究资料评估专家。请根据任务覆盖度、"
                        "来源可靠性、信息时效性和证据充分程度评分。"
                        "给出 0 到 100 的整数分数，并给出一条具体、"
                        "可用于下一轮搜索的意见。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"研究主题：{topic}\n\n"
                        f"研究任务：\n{task_list}\n\n"
                        f"已收集资料：\n{research_content}\n\n"
                        f"来源：\n{source_list}"
                    ),
                },
            ],
            text_format=ResearchEvaluation,
        )

        evaluation = response.output_parsed
        if evaluation is None:
            raise RuntimeError("Research Evaluator 没有返回可解析的结果。")

        return evaluation

    def write_report(
        self,
        topic: str,
        research_content: str,
        sources: list[str],
        review_comment: str | None = None,
    ) -> str:
        """Ask the model to write or revise a Markdown research report."""

        client, model = self._get_client_and_model()
        revision_request = ""
        if review_comment:
            revision_request = f"\n\n上一轮审核意见：{review_comment}\n请针对意见改进报告。"

        source_list = "\n".join(f"- {url}" for url in sources)

        response = client.responses.create(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "你是一名严谨的中文研究报告作者。请根据给定资料撰写结构"
                        "清晰的 Markdown 报告，不要编造资料中没有的数据或来源。"
                        "关键事实使用 Markdown 链接引用，并在末尾保留来源清单。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"研究主题：{topic}\n\n"
                        f"已有研究资料：\n{research_content}\n\n"
                        f"可引用来源：\n{source_list}"
                        f"{revision_request}"
                    ),
                },
            ],
        )

        draft = (response.output_text or "").strip()
        if not draft:
            raise RuntimeError("Writer 没有返回报告内容。")

        return draft

    def review_report(self, draft: str) -> ReportReview:
        """Ask the model to score a report and return structured feedback."""

        client, model = self._get_client_and_model()
        response = client.responses.parse(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "你是一名研究报告审核专家。请从结构完整性、内容深度、"
                        "逻辑性和信息充分程度四方面审核报告，给出 0 到 100 的"
                        "整数评分和一条具体、可执行的修改意见。"
                    ),
                },
                {"role": "user", "content": draft},
            ],
            text_format=ReportReview,
        )

        review = response.output_parsed
        if review is None:
            raise RuntimeError("Reviewer 没有返回可解析的审核结果。")

        return review

    @staticmethod
    def _extract_source_urls(response) -> list[str]:
        """Collect unique source URLs from web search tool calls."""

        source_urls = []

        for output_item in response.output:
            if getattr(output_item, "type", None) != "web_search_call":
                continue

            action = getattr(output_item, "action", None)
            sources = getattr(action, "sources", None) or []
            for source in sources:
                url = getattr(source, "url", None)
                if url and url not in source_urls:
                    source_urls.append(url)

        return source_urls

    def _get_client_and_model(self, for_search: bool = False):
        """Create the API client lazily so imports and tests need no API key."""

        requested_model = self._search_model if for_search else self._model
        if self._client is not None and requested_model is not None:
            return self._client, requested_model

        settings = Settings.from_env()

        if self._client is None:
            self._client = OpenAI(api_key=settings.openai_api_key)
        if self._model is None:
            self._model = settings.openai_model
        if self._search_model is None:
            self._search_model = settings.openai_search_model

        requested_model = self._search_model if for_search else self._model
        return self._client, requested_model


llm = OpenAIResearchService()
