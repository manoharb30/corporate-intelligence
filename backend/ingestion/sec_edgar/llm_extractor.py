"""LLM-based extraction using Claude with strict Pydantic validation."""

import json
import logging
from typing import Optional, Type, TypeVar

from anthropic import Anthropic
from pydantic import BaseModel, ValidationError

from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMExtractor:
    """Extract structured data from text using Claude with Pydantic validation."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        if not self.api_key:
            logger.warning("No Anthropic API key configured. LLM extraction will fail.")
            self.client = None
        else:
            self.client = Anthropic(api_key=self.api_key)

    def extract(
        self,
        text: str,
        output_model: Type[T],
        extraction_prompt: str,
        max_tokens: int = 4096,
    ) -> Optional[T]:
        """
        Extract structured data using Claude.

        Args:
            text: The text to extract from
            output_model: Pydantic model class for validation
            extraction_prompt: Instructions for extraction
            max_tokens: Maximum tokens in response

        Returns:
            Validated Pydantic model or None if extraction/validation fails
        """
        if not self.client:
            logger.error("LLM extraction called but no API key configured")
            return None

        # Build the full prompt
        full_prompt = f"""{extraction_prompt}

TEXT TO EXTRACT FROM:
---
{text[:50000]}  # Limit text length to avoid token limits
---

IMPORTANT: Respond with valid JSON only, no markdown formatting, no explanation.
The JSON must conform to this schema: {output_model.model_json_schema()}
"""

        try:
            response = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=max_tokens,
                messages=[
                    {
                        "role": "user",
                        "content": full_prompt,
                    }
                ],
            )

            # Extract text from response
            response_text = response.content[0].text.strip()

            # Try to parse JSON (handle markdown code blocks if present)
            if response_text.startswith("```"):
                # Remove markdown code block
                lines = response_text.split("\n")
                json_lines = []
                in_block = False
                for line in lines:
                    if line.startswith("```"):
                        in_block = not in_block
                        continue
                    if in_block:
                        json_lines.append(line)
                response_text = "\n".join(json_lines)

            data = json.loads(response_text)
            return output_model.model_validate(data)

        except json.JSONDecodeError as e:
            logger.warning(f"LLM response is not valid JSON: {e}")
            logger.debug(f"Response was: {response_text[:500]}")
            return None
        except ValidationError as e:
            logger.warning(f"LLM extraction failed Pydantic validation: {e}")
            return None
        except Exception as e:
            logger.error(f"LLM extraction error: {e}")
            return None

    def extract_ownership(self, html_text: str) -> Optional[list[dict]]:
        """Extract beneficial ownership data from filing text."""
        prompt = """Extract all beneficial ownership information from this SEC filing.

For each owner, extract:
- owner_name: Full name of the beneficial owner
- owner_type: "person" or "company"
- shares_owned: Number of shares owned (integer, or null if not specified)
- percentage: Ownership percentage (float between 0-100, or null if not specified)
- is_beneficial: true if this is beneficial ownership
- is_direct: true if direct ownership, false if indirect

Return a JSON object with this structure:
{
    "owners": [
        {
            "owner_name": "...",
            "owner_type": "person",
            "shares_owned": 1000000,
            "percentage": 5.5,
            "is_beneficial": true,
            "is_direct": true
        }
    ],
    "confidence": 0.95
}

Only include owners with specific ownership data. Set confidence based on data clarity."""

        from app.models.extraction_models import LLMOwnershipRequest

        class OwnershipResponse(BaseModel):
            owners: list[dict]
            confidence: float

        result = self.extract(html_text, OwnershipResponse, prompt)
        if result:
            return result.owners
        return None

    def extract_subsidiaries(self, html_text: str) -> Optional[list[dict]]:
        """Extract subsidiary information from 10-K Exhibit 21."""
        prompt = """Extract all subsidiary companies from this SEC 10-K Exhibit 21.

For each subsidiary, extract:
- name: Full legal name of the subsidiary
- jurisdiction: State or country of incorporation (e.g., "Delaware", "Cayman Islands")
- ownership_percentage: Ownership percentage if specified (float 0-100, or null)
- is_wholly_owned: true if 100% owned or described as "wholly owned"

Return a JSON object with this structure:
{
    "subsidiaries": [
        {
            "name": "Subsidiary Corp",
            "jurisdiction": "Delaware",
            "ownership_percentage": 100.0,
            "is_wholly_owned": true
        }
    ],
    "confidence": 0.95
}

Include all subsidiaries listed. Set confidence based on data clarity."""

        class SubsidiaryResponse(BaseModel):
            subsidiaries: list[dict]
            confidence: float

        result = self.extract(html_text, SubsidiaryResponse, prompt)
        if result:
            return result.subsidiaries
        return None

    def extract_officers(self, html_text: str) -> Optional[list[dict]]:
        """Extract officers and directors from DEF 14A."""
        prompt = """Extract all executive officers and directors from this SEC proxy statement (DEF 14A).

For each person, extract:
- name: Full name
- title: Job title or position (e.g., "Chief Executive Officer", "Director")
- is_director: true if they serve on the board of directors
- is_officer: true if they are an executive officer
- is_executive: true if they are a named executive officer (NEO)
- age: Age if specified (integer or null)

Return a JSON object with this structure:
{
    "officers": [
        {
            "name": "John Smith",
            "title": "Chief Executive Officer",
            "is_director": true,
            "is_officer": true,
            "is_executive": true,
            "age": 55
        }
    ],
    "confidence": 0.95
}

Include all officers and directors. Set confidence based on data clarity."""

        class OfficerResponse(BaseModel):
            officers: list[dict]
            confidence: float

        result = self.extract(html_text, OfficerResponse, prompt)
        if result:
            return result.officers
        return None
