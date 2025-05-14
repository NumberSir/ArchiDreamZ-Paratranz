import httpx

from src.config import settings
from src.core import Project
from src.paratranz import Paratranz


def main():
    project = Project()
    project.clean(
        settings.root / settings.filepath.converted,
        settings.root / settings.filepath.download,
        settings.root / settings.filepath.result,
    )
    project.convert()

    with httpx.Client() as client:
        paratranz = Paratranz(client=client)
        paratranz.download()

    project.restore()


if __name__ == '__main__':
    main()