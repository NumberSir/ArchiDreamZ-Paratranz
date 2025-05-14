import httpx

from src.config import settings
from src.core import Project
from src.paratranz import Paratranz


def main():
    project = Project()
    project.clean(
        settings.root / settings.file.converted,
        settings.root / settings.file.download,
        settings.root / settings.file.result,
    )
    project.convert()

    with httpx.Client() as client:
        paratranz = Paratranz(client=client)
        paratranz.download()

    project.restore()


if __name__ == '__main__':
    main()