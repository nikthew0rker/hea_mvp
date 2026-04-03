import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hea.graphs.specialist.nodes import route_specialist_message, update_draft
from hea.shared.models import default_draft


async def main():
    state = {"conversation_id": "demo", "language": "en", "user_message": "на русском", "draft": default_draft()}
    routed = await route_specialist_message(state)
    assert routed["language"] == "ru"
    assert routed["next_action"] == "ACK_LANGUAGE"

    state = {"conversation_id": "demo", "language": "ru", "user_message": "ей", "draft": default_draft()}
    routed = await route_specialist_message(state)
    assert routed["next_action"] == "SHOW_HELP"

    state = {"conversation_id": "demo", "language": "ru", "user_message": "topic diabets", "draft": default_draft()}
    updated = await update_draft(state)
    draft = updated["draft"]
    assert draft["understood"]["topic"] == "diabetes"
    assert len(draft["candidate_questions"]) >= 1

    noisy = '''
    Тема диабет
    - question: dry mouth?
    - question: frequent thirst?
    low risk: 0-2
    elevated risk: 3-10
    '''
    state = {"conversation_id": "demo", "language": "ru", "user_message": noisy, "draft": default_draft()}
    updated = await update_draft(state)
    draft = updated["draft"]
    assert draft["understood"]["topic"] == "diabetes"
    assert len(draft["candidate_questions"]) >= 2

    print("specialist smoke check passed")


if __name__ == "__main__":
    asyncio.run(main())
