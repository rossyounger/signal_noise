from __future__ import annotations

import logging

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

async def check_hypothesis(
    segment_text: str,
    topic_name: str,
    user_hypothesis: str,
    model_name: str = "gpt-4o-mini"
) -> str:
    """
    Analyzes a segment to determine if it confirms, refutes, or nuances a user's hypothesis about a topic.
    Returns a short analysis text.
    """
    
    llm = ChatOpenAI(model=model_name, temperature=0.0)
    parser = StrOutputParser()

    system_prompt = (
        "You are a rigorous analyst verifying a hypothesis against a specific text segment. "
        "Your goal is to determine the relationship between the evidence and the hypothesis.\n\n"
        "Output Guidelines:\n"
        "- Start with one of these bolded verdicts: **CONFIRMS**, **REFUTES**, **NUANCES**, or **IRRELEVANT**.\n"
        "- Follow with a concise explanation (2-3 sentences) citing specific parts of the segment.\n"
        "- Maintain a neutral, objective tone."
    )

    human_prompt = (
        "TOPIC: {topic_name}\n"
        "HYPOTHESIS: {user_hypothesis}\n\n"
        "EVIDENCE (Segment):\n{segment_text}\n\n"
        "Analysis:"
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", human_prompt),
    ])

    chain = prompt | llm | parser

    logger.info(f"Checking hypothesis for topic '{topic_name}' against segment (length {len(segment_text)}).")

    try:
        analysis_text = await chain.ainvoke({
            "segment_text": segment_text,
            "topic_name": topic_name,
            "user_hypothesis": user_hypothesis
        })
        return analysis_text
    except Exception as e:
        logger.error(f"Error checking hypothesis: {e}")
        return "Error: Could not analyze hypothesis."

