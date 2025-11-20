from openai import AsyncOpenAI
from typing import Dict, Any
import json
from app.core.config import settings

class MedicationService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
    
    def get_medication_prompt(self, medication_name: str, strength: str) -> str:
        return f"""
You are a medical information assistant. Provide comprehensive, accurate information about the medication {medication_name} {strength}.

Return ONLY a valid JSON object (no markdown, no backticks) with this exact structure:

{{
  "genericName": "string",
  "drugClass": "string",
  "manufacturer": "string (use 'Generic' if unknown)",
  "description": "string (purpose of medication)",
  "usage": {{
    "instructions": ["array of 5 specific usage instructions"],
    "missedDose": "string (what to do if dose is missed)",
    "storage": "string (storage instructions)"
  }},
  "sideEffects": {{
    "common": ["array of 5-6 common side effects"],
    "serious": ["array of 4-5 serious side effects"],
    "whenToCall": "string (when to contact doctor)"
  }},
  "interactions": {{
    "drugs": ["array of 5 common drug interactions"],
    "food": ["array of 2-3 food/drink interactions"],
    "conditions": ["array of 5 medical conditions to be aware of"]
  }},
  "warnings": ["array of 5 important warnings"]
}}

Be specific, accurate, and use clear medical terminology appropriate for patients.
"""
    
    async def fetch_medication_details(
        self, 
        medication_name: str, 
        strength: str
    ) -> Dict[str, Any]:
        """Fetch medication details from OpenAI API"""
        try:
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a medical information expert. Provide accurate, patient-friendly medication information in JSON format only."
                    },
                    {
                        "role": "user",
                        "content": self.get_medication_prompt(medication_name, strength)
                    }
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Clean up response (remove potential markdown)
            cleaned_response = response_text.replace("```json", "").replace("```", "").strip()
            
            # Parse JSON
            medication_data = json.loads(cleaned_response)
            
            return medication_data
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse OpenAI response: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to fetch medication details: {str(e)}")

medication_service = MedicationService()