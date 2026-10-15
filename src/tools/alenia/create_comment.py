"""
Real implementation of the ORG tool `create_comment`, backed by OpenProject.
"""

from openproject_client import create_comment as _create_comment_on_openproject


def create_comment(ticket_id: str, comment: str) -> None:
    _create_comment_on_openproject(int(ticket_id), comment)