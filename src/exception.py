class ProjectStructureException(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__("File does not exist!", *args, **kwargs)


class UnknownFileTypeException(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__("Unknown file type", *args, **kwargs)


__all__ = [
    "ProjectStructureException",
    "UnknownFileTypeException",
]