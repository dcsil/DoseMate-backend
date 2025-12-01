import json
from types import SimpleNamespace

import pytest

from app.medications.services import MedicationService


class FakeCompletions:
    """Fake object for client.chat.completions"""

    def __init__(self, content=None, error: Exception | None = None):
        self._content = content
        self._error = error

    async def create(self, **kwargs):
        if self._error:
            # Simulate an error coming from the OpenAI client
            raise self._error

        # Shape the object like response.choices[0].message.content
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self._content)
                )
            ]
        )


class FakeChat:
    def __init__(self, content=None, error: Exception | None = None):
        self.completions = FakeCompletions(content, error)


class FakeClient:
    """Fake AsyncOpenAI client with only .chat.completions.create"""

    def __init__(self, content=None, error: Exception | None = None):
        self.chat = FakeChat(content, error)


def test_get_medication_prompt_includes_name_and_strength():
    service = MedicationService()
    prompt = service.get_medication_prompt("Tylenol", "500mg")

    # Basic sanity checks: name, strength, and some JSON keys
    assert "Tylenol" in prompt
    assert "500mg" in prompt
    assert '"genericName"' in prompt
    assert '"warnings"' in prompt
    assert '"usage"' in prompt


@pytest.mark.anyio("asyncio")
async def test_fetch_medication_details_parses_valid_json():
    # Fake JSON from "OpenAI"
    fake_json = json.dumps(
        {
            "genericName": "Acetaminophen",
            "drugClass": "Analgesic",
            "manufacturer": "Generic",
            "description": "Pain reliever and fever reducer",
            "usage": {
                "instructions": ["Use as directed"] * 5,
                "missedDose": "Take as soon as you remember",
                "storage": "Store at room temperature",
            },
            "sideEffects": {
                "common": ["Nausea"] * 5,
                "serious": ["Liver damage"] * 4,
                "whenToCall": "If you experience severe symptoms",
            },
            "interactions": {
                "drugs": ["Warfarin"] * 5,
                "food": ["Alcohol"] * 2,
                "conditions": ["Liver disease"] * 5,
            },
            "warnings": ["Do not exceed recommended dose"] * 5,
        }
    )

    service = MedicationService()
    service.client = FakeClient(content=fake_json)

    result = await service.fetch_medication_details("Tylenol", "500mg")

    assert result["genericName"] == "Acetaminophen"
    assert result["drugClass"] == "Analgesic"
    assert result["warnings"]
    assert len(result["usage"]["instructions"]) == 5


@pytest.mark.anyio("asyncio")
async def test_fetch_medication_details_strips_markdown_wrappers():
    # Simulate OpenAI returning markdown-wrapped JSON
    wrapped = "```json\n" + json.dumps({"genericName": "Acetaminophen"}) + "\n```"

    service = MedicationService()
    service.client = FakeClient(content=wrapped)

    result = await service.fetch_medication_details("Tylenol", "500mg")

    assert result["genericName"] == "Acetaminophen"


@pytest.mark.anyio("asyncio")
async def test_fetch_medication_details_raises_value_error_on_bad_json():
    # This will cause json.loads(...) to raise JSONDecodeError
    bad_content = "not-json-at-all"

    service = MedicationService()
    service.client = FakeClient(content=bad_content)

    with pytest.raises(ValueError) as excinfo:
        await service.fetch_medication_details("Tylenol", "500mg")

    assert "Failed to parse OpenAI response" in str(excinfo.value)


@pytest.mark.anyio("asyncio")
async def test_fetch_medication_details_wraps_unexpected_errors():
    # Simulate an unexpected error coming from the OpenAI client
    service = MedicationService()
    service.client = FakeClient(content=None, error=RuntimeError("OpenAI down"))

    with pytest.raises(Exception) as excinfo:
        await service.fetch_medication_details("Tylenol", "500mg")

    msg = str(excinfo.value)
    assert "Failed to fetch medication details" in msg
    assert "OpenAI down" in msg
