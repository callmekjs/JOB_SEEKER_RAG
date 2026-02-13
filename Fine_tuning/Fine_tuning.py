"""
Fine_tuning: RAG(특히 LLM 답변 생성) 파인튜닝 시 사용할 규칙 및 프롬프트.
팀장님 지시: JD는 의미 보존을 전제로 자연어 형태로 변환할 수 있으나,
             정보 삭제나 추론적 재작성은 금지한다.
"""

# 팀장님 원칙 (파인튜닝 데이터·시스템 프롬프트에 반드시 반영)
JD_RAG_RULE = (
    "JD(채용 공고)는 의미 보존을 전제로 자연어 형태로 변환할 수 있으나, "
    "정보 삭제나 추론적 재작성은 금지한다. "
    "원문에 없는 내용을 추측·보강하지 말고, 있는 정보만 요약·정리하여 답하라."
)


def get_finetune_system_prompt() -> str:
    """
    파인튜닝용 시스템 프롬프트. 팀장님 원칙을 반드시 포함.
    LLM 파인튜닝 시 system 메시지 또는 학습 지침으로 사용.
    """
    return (
        "당신은 채용 공고(JD)를 참고하여 질문에 답하는 도우미입니다.\n\n"
        "【반드시 지킬 원칙】\n"
        "- JD는 의미 보존을 전제로 자연어 형태로 변환할 수 있습니다(요약·정리).\n"
        "- 정보 삭제는 금지합니다. 원문에 있는 내용을 누락하지 마세요.\n"
        "- 추론적 재작성은 금지합니다. 원문에 없는 내용을 추측하거나 보강하지 마세요.\n"
        "- 아래 채용 공고 내용만을 참고하여 질문에 간결하게 답해주세요."
    )


def build_finetune_messages_example(
    query: str,
    context: str,
    assistant_answer: str,
) -> list[dict[str, str]]:
    """
    OpenAI 파인튜닝용 messages 예시 1건 생성.
    팀장님 원칙이 반영된 system + (user: 질문+context, assistant: 답변) 형태.

    Args:
        query: 사용자 질문.
        context: 참고한 JD(채용 공고) 텍스트.
        assistant_answer: 의미 보존·삭제/추론 금지 원칙에 맞게 작성한 정답 답변.

    Returns:
        [{"role": "system", "content": ...}, {"role": "user", "content": ...}, {"role": "assistant", "content": ...}]
    """
    system = get_finetune_system_prompt()
    user = (
        "다음 채용 공고 내용을 참고해서 질문에 답해주세요.\n\n"
        "--- 채용 공고 ---\n"
        f"{context}\n"
        "--- 끝 ---\n\n"
        f"질문: {query}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant_answer},
    ]


def get_rule_for_data_guideline() -> str:
    """
    파인튜닝 데이터(정답 답변) 작성 가이드라인으로 쓸 문구.
    라벨러/작성자가 정답 답변을 만들 때 참고하도록 사용.
    """
    return (
        "정답 답변 작성 시 반드시 지킬 것:\n"
        "- JD 의미 보존: 원문의 의미를 유지한 채 자연어로 요약·정리 가능.\n"
        "- 정보 삭제 금지: 원문에 있는 정보를 빠뜨리지 말 것.\n"
        "- 추론적 재작성 금지: 원문에 없는 내용을 추측·덧붙이지 말 것."
    )
