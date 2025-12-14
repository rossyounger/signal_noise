from __future__ import annotations

import logging
from typing import List, Optional

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class HypothesisSuggestionModel(BaseModel):
    hypothesis_id: Optional[str] = Field(None, description="UUID of the existing hypothesis, or null if new.")
    hypothesis_text: str = Field(..., description="The testable proposition/hypothesis.")
    source: str = Field(..., description="Must be 'existing' or 'generated'.")
    description: Optional[str] = Field(None, description="Context or rationale for the hypothesis.")
    analysis_text: Optional[str] = Field(None, description="Draft analysis of how the segment relates to this hypothesis.")


class SuggestionResponse(BaseModel):
    suggestions: List[HypothesisSuggestionModel]


async def suggest_hypotheses(
    pool: AsyncConnectionPool,
    segment_text: str,
    model_name: str = "gpt-4o-mini"
) -> List[HypothesisSuggestionModel]:
    """
    Suggests hypotheses for a segment by:
    1. Fetching all existing hypotheses from DB.
    2. Using an LLM to match the segment against existing hypotheses and generate new ones.
    """
    
    # 1. Fetch existing hypotheses
    existing_hypotheses = []
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    id,
                    hypothesis_text,
                    description
                FROM hypotheses
                ORDER BY updated_at DESC
                """
            )
            rows = await cur.fetchall()
            for r in rows:
                existing_hypotheses.append({
                    "id": str(r[0]),
                    "hypothesis_text": r[1] or "",
                    "description": r[2] or ""
                })

    # 2. Construct LLM Prompt
    llm = ChatOpenAI(model=model_name, temperature=0.0)
    parser = JsonOutputParser(pydantic_object=SuggestionResponse)

    system_prompt = (
        "You are an expert analyst helping to test hypotheses against evidence. "
        "Your task is to identify which hypotheses are relevant to a given text segment.\n\n"
        "You have a list of EXISTING HYPOTHESES. "
        "For each existing hypothesis, decide if the segment provides evidence for or against it. "
        "If the segment suggests important propositions NOT covered by existing hypotheses, propose NEW hypotheses.\n\n"
        "For 'existing' hypotheses:\n"
        "- Use the exact provided hypothesis_id.\n"
        "- Return the current description unless the segment strongly suggests an update is needed (rare).\n"
        "- Provide a brief analysis_text explaining how the segment relates to this hypothesis.\n\n"
        "For 'generated' (new) hypotheses:\n"
        "- Set hypothesis_id to null.\n"
        "- Create a clear, testable hypothesis statement.\n"
        "- Write a short description providing context.\n"
        "- Provide analysis_text explaining what the segment suggests about this hypothesis.\n\n"
        "Return a JSON object with a 'suggestions' key containing a list of hypothesis objects."
    )

    human_prompt = (
        "SEGMENT TEXT:\n{segment_text}\n\n"
        "EXISTING HYPOTHESES:\n{existing_hypotheses_json}\n\n"
        "Please analyze and return JSON."
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", human_prompt),
    ])

    chain = prompt | llm | parser

    # 3. Run LLM
    logger.info(f"Generating hypothesis suggestions for segment (length {len(segment_text)}) with {len(existing_hypotheses)} existing hypotheses.")
    
    try:
        result = await chain.ainvoke({
            "segment_text": segment_text,
            "existing_hypotheses_json": str(existing_hypotheses)
        })
        
        suggestions = []
        for item in result.get("suggestions", []):
            # validations/cleanups
            if item.get("source") not in ["existing", "generated"]:
                item["source"] = "generated"
            
            suggestions.append(HypothesisSuggestionModel(**item))
            
        return suggestions

    except Exception as e:
        logger.error(f"Error generating hypothesis suggestions: {e}")
        return []
