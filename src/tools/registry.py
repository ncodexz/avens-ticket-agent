"""
THE SWITCH. This is the only file in the whole project that knows whether
we're running against our own mocks or against Alenia's real tools.

Day of the hackathon: change PROVIDER to "alenia", write the 4 functions
inside tools/alenia/ so they match tools/base.py's contract, done. Nothing
in agent/ or demo/ needs to change.
"""

PROVIDER = "mock"  # "mock" | "alenia"


def get_tools():
    if PROVIDER == "mock":
        from tools.mock.read_ticket import read_ticket
        from tools.mock.retrieve_similar_tickets import retrieve_similar_tickets
        from tools.mock.create_comment import create_comment
        from tools.mock.update_status import update_status
    elif PROVIDER == "alenia":
        from tools.alenia.read_ticket import read_ticket
        from tools.alenia.retrieve_similar_tickets import retrieve_similar_tickets
        from tools.alenia.create_comment import create_comment
        from tools.alenia.update_status import update_status
    else:
        raise ValueError(f"Unknown PROVIDER: {PROVIDER}")

    return read_ticket, retrieve_similar_tickets, create_comment, update_status