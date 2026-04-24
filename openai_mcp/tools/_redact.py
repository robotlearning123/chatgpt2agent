import re


def redact(s: object) -> object:
    if not isinstance(s, str):
        return s
    s = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "<EMAIL>", s)
    s = re.sub(r"\+?\d[\d ()\-]{8,}\d", "<PHONE>", s)
    return s
