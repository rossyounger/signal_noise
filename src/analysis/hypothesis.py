from __future__ import annotations

import logging
from typing import Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from .reference_fetcher import fetch_reference_content, get_cached_reference, cache_reference_content

logger = logging.getLogger(__name__)


async def check_hypothesis(
    segment_text: str,
    hypothesis_text: str,
    hypothesis_description: Optional[str] = None,
    reference_url: Optional[str] = None,
    include_full_reference: bool = False,
    hypothesis_id: Optional[str] = None,
    db_connection = None,
    model_name: str = "gpt-4o-mini"
) -> str:
    """
    Analyzes a segment to determine if it confirms, refutes, or nuances a hypothesis.
    Returns a short analysis text with a verdict.
    
    Args:
        segment_text: The text segment to analyze as evidence
        hypothesis_text: The hypothesis statement to test
        hypothesis_description: Optional detailed description/summary of the hypothesis
        reference_url: Optional URL to full reference document
        include_full_reference: If True and reference_url provided, fetch and include full document
        hypothesis_id: UUID of hypothesis (required for caching if include_full_reference=True)
        db_connection: Database connection (required for caching if include_full_reference=True)
        model_name: OpenAI model to use for analysis
        
    Returns:
        Analysis text with verdict (CONFIRMS/REFUTES/NUANCES/IRRELEVANT) and explanation
    """
    
    llm = ChatOpenAI(model=model_name, temperature=0.0)
    parser = StrOutputParser()
    
    # Build hypothesis context based on available information and user preference
    hypothesis_context = hypothesis_text
    reference_text = None
    
    if hypothesis_description:
        hypothesis_context += f"\n\nContext: {hypothesis_description}"
    
    # Fetch full reference if requested and available
    if include_full_reference and reference_url:
        if not hypothesis_id or not db_connection:
            logger.warning("Cannot fetch reference: hypothesis_id and db_connection required for caching")
        else:
            # Try cache first
            reference_text = await get_cached_reference(hypothesis_id, db_connection)
            
            # Fetch if not cached
            if not reference_text:
                logger.info(f"Fetching full reference from {reference_url}")
                reference_text = await fetch_reference_content(reference_url)
                
                # Cache the fetched content
                if reference_text:
                    await cache_reference_content(hypothesis_id, reference_text, db_connection)
            
            # Add reference to context if successfully fetched
            if reference_text:
                hypothesis_context += f"\n\n--- FULL REFERENCE DOCUMENT ---\n{reference_text}"
                logger.info(f"Including full reference ({len(reference_text)} chars) in analysis")
            else:
                logger.warning(f"Failed to fetch reference from {reference_url}, falling back to summary")

    system_prompt = (
        "You are a rigorous analyst verifying a hypothesis against a specific text segment. "
        "Your goal is to determine the relationship between the evidence and the hypothesis.\n\n"
        "Output Guidelines:\n"
        "- Start with one of these bolded verdicts: **CONFIRMS**, **REFUTES**, **NUANCES**, or **IRRELEVANT**.\n"
        "- Follow with a concise explanation (2-3 sentences) citing specific parts of the segment.\n"
        "- Maintain a neutral, objective tone."
    )

    human_prompt = (
        "HYPOTHESIS: {hypothesis_context}\n\n"
        "EVIDENCE (Segment):\n{segment_text}\n\n"
        "Analysis:"
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", human_prompt),
    ])

    chain = prompt | llm | parser

    analysis_mode = "with full reference" if reference_text else "with summary only"
    logger.info(f"Checking hypothesis against segment (length {len(segment_text)}) {analysis_mode}.")

    try:
        analysis_text = await chain.ainvoke({
            "segment_text": segment_text,
            "hypothesis_context": hypothesis_context
        })
        return analysis_text
    except Exception as e:
        logger.error(f"Error checking hypothesis: {e}")
        return "Error: Could not analyze hypothesis."
