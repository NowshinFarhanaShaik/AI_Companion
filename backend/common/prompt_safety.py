def escape_data(text: str) -> str:
    """Untrusted text goes into prompts inside XML-style data blocks; escaping stops it closing its block."""
    return text.replace("<", "&lt;").replace(">", "&gt;")
