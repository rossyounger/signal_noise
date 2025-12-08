from __future__ import annotations

import logging
from typing import List, Optional

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Redefine here to avoid circular imports if api.py imports this module
class TopicSuggestionModel(BaseModel):
    topic_id: Optional[str] = Field(None, description="UUID of the existing topic, or null if new.")
    name: str = Field(..., description="Name of the topic.")
    source: str = Field(..., description="Must be 'existing' or 'generated'.")
    description: Optional[str] = Field(None, description="Description of the topic context.")
    user_hypothesis: Optional[str] = Field(None, description="Current user hypothesis for this topic.")
    summary_text: Optional[str] = Field(None, description="Draft analysis of how the segment relates to this topic.")

class SuggestionResponse(BaseModel):
    suggestions: List[TopicSuggestionModel]


async def suggest_topics(
    pool: AsyncConnectionPool,
    segment_text: str,
    model_name: str = "gpt-4o-mini"
) -> List[TopicSuggestionModel]:
    """
    Suggests topics for a segment by:
    1. Fetching the latest state of all existing topics from DB.
    2. Using an LLM to match the segment against existing topics and generate new ones.
    """
    
    # 1. Fetch latest topics state
    # We want the most recent history entry for each topic_id
    existing_topics = []
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT DISTINCT ON (topic_id)
                    topic_id,
                    name,
                    description,
                    user_hypothesis
                FROM topics_history
                ORDER BY topic_id, created_at DESC
                """
            )
            rows = await cur.fetchall()
            # Map to a list of dicts for the prompt
            for r in rows:
                existing_topics.append({
                    "id": str(r[0]),
                    "name": r[1],
                    "description": r[2] or "",
                    "hypothesis": r[3] or ""
                })

    # 2. Construct LLM Prompt
    llm = ChatOpenAI(model=model_name, temperature=0.0)
    parser = JsonOutputParser(pydantic_object=SuggestionResponse)

    system_prompt = (
        "You are an expert content analyst helping to organize a knowledge base. "
        "Your task is to identify which topics are relevant to a given text segment.\n\n"
        "You have a list of EXISTING TOPICS. "
        "For each existing topic, decide if the segment is relevant to it. "
        "If the segment contains important concepts NOT covered by existing topics, propose NEW topics.\n\n"
        "For 'existing' topics:\n"
        "- Use the exact provided topic_id.\n"
        "- Return the current description/hypothesis unless the segment strongly suggests an update is needed (rare).\n\n"
        "For 'generated' (new) topics:\n"
        "- Set topic_id to null.\n"
        "- Create a concise, meaningful name.\n"
        "- Write a short description of the topic.\n"
        "- Formulate a tentative 'user_hypothesis' based on what the text implies about this topic.\n\n"
        "Return a JSON object with a 'suggestions' key containing a list of topic objects."
    )

    human_prompt = (
        "SEGMENT TEXT:\n{segment_text}\n\n"
        "EXISTING TOPICS:\n{existing_topics_json}\n\n"
        "Please analyze and return JSON."
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", human_prompt),
    ])

    chain = prompt | llm | parser

    # 3. Run LLM
    logger.info(f"Generating topic suggestions for segment (length {len(segment_text)}) with {len(existing_topics)} existing topics.")
    
    try:
        result = await chain.ainvoke({
            "segment_text": segment_text,
            "existing_topics_json": str(existing_topics) # Passing as string representation for the prompt
        })
        
        suggestions = []
        for item in result.get("suggestions", []):
            # validations/cleanups
            if item.get("source") not in ["existing", "generated"]:
                item["source"] = "generated"
            
            suggestions.append(TopicSuggestionModel(**item))
            
        return suggestions

    except Exception as e:
        logger.error(f"Error generating topic suggestions: {e}")
        # Fallback: return empty list or maybe just the existing topics? 
        # For now, return empty list to avoid bad data.
        return []

