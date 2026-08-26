"""Simple test doubles for services that would otherwise call external APIs."""

from threading import Lock
from time import sleep

from app.llm import ReportReview, ResearchEvaluation, ResearchResult


class FakeResearchLLM:
    """Return predictable data without making an OpenAI API request."""

    def __init__(
        self,
        review_score: int = 85,
        research_scores: list[int] | None = None,
    ) -> None:
        self.review_score = review_score
        self.review_comment = "测试审核意见。"
        self.research_scores = research_scores or [85]
        self.plan_calls = 0
        self.research_calls = 0
        self.research_evaluation_calls = 0
        self.last_research_feedback = ""
        self.last_review_comment: str | None = None
        self.last_sources: list[str] = []
        self._counter_lock = Lock()

    def create_plan(self, topic: str) -> list[str]:
        self.plan_calls += 1
        return [
            f"分析 {topic} 的背景",
            "梳理当前应用",
            "总结主要问题",
            "判断未来趋势",
        ]

    def research(
        self,
        topic: str,
        tasks: list[str],
        existing_research: str = "",
        evaluation_comment: str = "",
    ) -> ResearchResult:
        with self._counter_lock:
            self.research_calls += 1
        self.last_research_feedback = evaluation_comment
        task_list = "、".join(tasks)
        return ResearchResult(
            content=f"{topic} 的测试研究资料：{task_list}",
            sources=["https://example.com/research"],
        )

    def evaluate_research(
        self,
        topic: str,
        tasks: list[str],
        research_content: str,
        sources: list[str],
    ) -> ResearchEvaluation:
        score_index = min(
            self.research_evaluation_calls,
            len(self.research_scores) - 1,
        )
        score = self.research_scores[score_index]
        self.research_evaluation_calls += 1
        comment = "研究资料已足够。"
        if score < 80:
            comment = "请补充更多可验证证据。"
        return ResearchEvaluation(
            score=score,
            comment=comment,
        )

    def write_report(
        self,
        topic: str,
        research_content: str,
        sources: list[str],
        review_comment: str | None = None,
        on_token=None,
    ) -> str:
        self.last_review_comment = review_comment
        self.last_sources = sources
        draft = f"# {topic}\n\n{research_content}\n\n## 初步结论\n\n测试结论。"
        if on_token is not None:
            for token in [f"# {topic}\n\n", research_content, "\n\n## 初步结论\n\n测试结论。"]:
                on_token(token)
        return draft

    def review_report(self, _draft: str) -> ReportReview:
        return ReportReview(
            score=self.review_score,
            comment=self.review_comment,
        )


class ParallelTrackingResearchLLM(FakeResearchLLM):
    """Record how many fake research calls overlap in time."""

    def __init__(self) -> None:
        super().__init__()
        self.active_research_calls = 0
        self.max_active_research_calls = 0
        self._active_lock = Lock()

    def research(self, *args, **kwargs) -> ResearchResult:
        with self._active_lock:
            self.active_research_calls += 1
            self.max_active_research_calls = max(
                self.max_active_research_calls,
                self.active_research_calls,
            )

        try:
            sleep(0.03)
            return super().research(*args, **kwargs)
        finally:
            with self._active_lock:
                self.active_research_calls -= 1
