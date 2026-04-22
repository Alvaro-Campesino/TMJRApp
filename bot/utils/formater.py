def bold(text: str) -> str:
    """
    Format text in bold.
    """
    return f"<b>{text}</b>"


def italic(text: str) -> str:
    """
    Format text in italic.
    """
    return f"<em>{text}<em>"


def strike(text: str) -> str:
    """
    Format text with strike.
    """
    return f"~~{text}~~"


def monospace(text: str) -> str:
    """
    Format text in monospace.
    """
    return f"```{text}```"
