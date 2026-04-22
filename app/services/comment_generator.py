from agents.comment_reply.agent import CommentReplyAgent
from app.llm_client import LLMClient
from app.schemas import CommentRunRequest


class CommentGenerator:
    def __init__(self) -> None:
        self.llm = LLMClient()
        self.agent = CommentReplyAgent(
            llm_client=self.llm,
        )
        self.agent_name = self.agent.agent_name

    async def generate(self, req: CommentRunRequest) -> tuple[list[str], str, str]:
        return await self.agent.generate(req)
