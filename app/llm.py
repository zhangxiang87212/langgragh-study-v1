"""LLM provider adapters used by the LangGraph nodes."""

from dataclasses import dataclass
from contextlib import contextmanager
from contextvars import ContextVar
import re
from threading import Lock
from typing import Callable, TypeVar

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from app.config import Settings


MAX_WEB_SEARCH_CALLS = 6
StructuredModel = TypeVar("StructuredModel", bound=BaseModel)
TokenCallback = Callable[[str], None]


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


def build_research_input(
    topic: str,
    tasks: list[str],
    existing_research: str,
    evaluation_comment: str,
) -> list[dict[str, str]]:
    """Build the shared web-search prompt for either provider."""

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

    return [
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
    ]


def extract_source_urls(response) -> list[str]:
    """Collect unique URLs from search metadata, citations, and text."""

    source_urls = []

    def add_url(url: str | None) -> None:
        if url and url not in source_urls:
            source_urls.append(url)

    for output_item in response.output:
        action = getattr(output_item, "action", None)
        sources = getattr(action, "sources", None) or []
        for source in sources:
            add_url(getattr(source, "url", None))

        content_parts = getattr(output_item, "content", None) or []
        for content_part in content_parts:
            annotations = getattr(content_part, "annotations", None) or []
            for annotation in annotations:
                add_url(getattr(annotation, "url", None))

    output_text = getattr(response, "output_text", "") or ""
    for url in re.findall(r"https?://[^\s\)\]\>\"]+", output_text):
        add_url(url.rstrip(".,;:，。；："))

    return source_urls


def collect_responses_text(stream, on_token: TokenCallback) -> str:
    """Collect Responses API text deltas while forwarding each token."""

    text_parts = []
    for event in stream:
        if getattr(event, "type", None) != "response.output_text.delta":
            continue

        token = getattr(event, "delta", "")
        if not token:
            continue

        text_parts.append(token)
        on_token(token)

    return "".join(text_parts).strip()


def collect_chat_completion_text(stream, on_token: TokenCallback) -> str:
    """Collect Chat Completions deltas while forwarding each token."""

    text_parts = []
    for chunk in stream:
        if not chunk.choices:
            continue

        token = getattr(chunk.choices[0].delta, "content", None)
        if not token:
            continue

        text_parts.append(token)
        on_token(token)

    return "".join(text_parts).strip()


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
        response = client.responses.create(
            model=model,
            tools=[{"type": "web_search"}],
            tool_choice="required",
            max_tool_calls=MAX_WEB_SEARCH_CALLS,
            include=["web_search_call.action.sources"],
            input=build_research_input(
                topic,
                tasks,
                existing_research,
                evaluation_comment,
            ),
        )

        content = (response.output_text or "").strip()
        if not content:
            raise RuntimeError("Researcher 没有返回研究资料。")

        sources = extract_source_urls(response)
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
        on_token: TokenCallback | None = None,
    ) -> str:
        """Ask the model to write or revise a Markdown research report."""

        client, model = self._get_client_and_model()
        revision_request = ""
        if review_comment:
            revision_request = f"\n\n上一轮审核意见：{review_comment}\n请针对意见改进报告。"

        source_list = "\n".join(f"- {url}" for url in sources)

        request = {
            "model": model,
            "input": [
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
        }

        if on_token is not None:
            request["stream"] = True

        response = client.responses.create(**request)
        if on_token is not None:
            draft = collect_responses_text(response, on_token)
        else:
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


class DeepSeekResearchService:
    """Use DeepSeek for generation, evaluation, and hosted web search."""

    def __init__(
        self,
        client=None,
        model: str | None = None,
    ) -> None:
        self._client = client
        self._model = model

    def create_plan(self, topic: str) -> list[str]:
        """Ask DeepSeek to split the topic into research tasks."""

        plan = self._create_structured_output(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一名研究规划专家。请把研究主题拆成 3 到 6 "
                        "个具体、互不重复且适合检索的研究任务。"
                        "只返回 JSON，格式为：{\"tasks\": [\"任务\"]}。"
                    ),
                },
                {"role": "user", "content": f"研究主题：{topic}"},
            ],
            output_type=ResearchPlan,
            operation_name="DeepSeek Planner",
        )
        return plan.tasks

    def research(
        self,
        topic: str,
        tasks: list[str],
        existing_research: str = "",
        evaluation_comment: str = "",
    ) -> ResearchResult:
        """Use DeepSeek Responses API and its server-side web search."""

        client, model = self._get_client_and_model()
        response = client.responses.create(
            model=model,
            tools=[{"type": "web_search"}],
            tool_choice="required",
            input=build_research_input(
                topic,
                tasks,
                existing_research,
                evaluation_comment,
            ),
        )

        content = (response.output_text or "").strip()
        if not content:
            raise RuntimeError("DeepSeek Researcher 没有返回研究资料。")

        sources = extract_source_urls(response)
        if not sources:
            raise RuntimeError("DeepSeek Researcher 没有返回可验证的网页来源。")

        return ResearchResult(content=content, sources=sources)

    def evaluate_research(
        self,
        topic: str,
        tasks: list[str],
        research_content: str,
        sources: list[str],
    ) -> ResearchEvaluation:
        """Ask DeepSeek whether the collected evidence is sufficient."""

        task_list = "\n".join(f"- {task}" for task in tasks)
        source_list = "\n".join(f"- {source}" for source in sources)
        return self._create_structured_output(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一名研究资料评估专家。请根据任务覆盖度、"
                        "来源可靠性、信息时效性和证据充分程度评分。"
                        "只返回 JSON，格式为："
                        "{\"score\": 80, \"comment\": \"具体意见\"}。"
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
            output_type=ResearchEvaluation,
            operation_name="DeepSeek Research Evaluator",
        )

    def write_report(
        self,
        topic: str,
        research_content: str,
        sources: list[str],
        review_comment: str | None = None,
        on_token: TokenCallback | None = None,
    ) -> str:
        """Ask DeepSeek to write or revise the report."""

        revision_request = ""
        if review_comment:
            revision_request = f"\n\n上一轮审核意见：{review_comment}\n请针对意见改进报告。"
        source_list = "\n".join(f"- {url}" for url in sources)
        return self._create_text_output(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一名严谨的中文研究报告作者。请根据给定资料撰写"
                        "结构清晰的 Markdown 报告，不要编造资料中没有的信息。"
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
            operation_name="DeepSeek Writer",
            on_token=on_token,
        )

    def review_report(self, draft: str) -> ReportReview:
        """Ask DeepSeek to review the report."""

        return self._create_structured_output(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一名研究报告审核专家。请从结构完整性、内容深度、"
                        "逻辑性和信息充分程度评分。只返回 JSON，格式为："
                        "{\"score\": 80, \"comment\": \"具体意见\"}。"
                    ),
                },
                {"role": "user", "content": draft},
            ],
            output_type=ReportReview,
            operation_name="DeepSeek Reviewer",
        )

    def _create_structured_output(
        self,
        messages: list[dict[str, str]],
        output_type: type[StructuredModel],
        operation_name: str,
    ) -> StructuredModel:
        """Request JSON and validate it with the same Pydantic models."""

        content = self._create_text_output(
            messages=messages,
            operation_name=operation_name,
            response_format={"type": "json_object"},
        )
        try:
            return output_type.model_validate_json(content)
        except ValidationError as error:
            raise RuntimeError(
                f"{operation_name} 没有返回符合结构的 JSON。"
            ) from error

    def _create_text_output(
        self,
        messages: list[dict[str, str]],
        operation_name: str,
        response_format: dict[str, str] | None = None,
        on_token: TokenCallback | None = None,
    ) -> str:
        """Call DeepSeek through its OpenAI-compatible Chat API."""

        client, model = self._get_client_and_model()
        request = {
            "model": model,
            "messages": messages,
            "stream": on_token is not None,
        }
        if response_format is not None:
            request["response_format"] = response_format

        response = client.chat.completions.create(**request)
        if on_token is not None:
            content = collect_chat_completion_text(response, on_token)
        else:
            content = (response.choices[0].message.content or "").strip()
        if not content:
            raise RuntimeError(f"{operation_name} 没有返回内容。")

        return content

    def _get_client_and_model(self):
        """Create the DeepSeek client lazily when used directly."""

        if self._client is not None and self._model is not None:
            return self._client, self._model

        settings = Settings.from_env()
        if self._client is None:
            self._client = OpenAI(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
            )
        if self._model is None:
            self._model = settings.deepseek_model

        return self._client, self._model


def create_research_service(settings: Settings):
    """Create one provider for every LLM operation, including research."""

    if settings.llm_provider == "openai":
        openai_client = OpenAI(api_key=settings.openai_api_key)
        return OpenAIResearchService(
            client=openai_client,
            model=settings.openai_model,
            search_model=settings.openai_search_model,
        )

    deepseek_client = OpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )
    return DeepSeekResearchService(
        client=deepseek_client,
        model=settings.deepseek_model,
    )


class ConfiguredResearchService:
    """Resolve a request-scoped web service or the CLI environment service."""

    def __init__(self) -> None:
        self._environment_service = None
        self._environment_lock = Lock()

    def __getattr__(self, method_name: str):
        service = _request_research_service.get()
        if service is None:
            service = self._get_environment_service()
        return getattr(service, method_name)

    def _get_environment_service(self):
        """Create the .env-backed service once for CLI compatibility."""

        if self._environment_service is not None:
            return self._environment_service
        with self._environment_lock:
            if self._environment_service is None:
                settings = Settings.from_env()
                self._environment_service = create_research_service(settings)
        return self._environment_service


_request_research_service: ContextVar[object | None] = ContextVar(
    "request_research_service",
    default=None,
)


@contextmanager
def use_research_service(settings: Settings):
    """Use one browser session's provider for the current graph execution."""

    service = create_research_service(settings)
    token = _request_research_service.set(service)
    try:
        yield
    finally:
        _request_research_service.reset(token)


llm = ConfiguredResearchService()
