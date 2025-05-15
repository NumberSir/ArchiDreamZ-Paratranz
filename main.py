import httpx

from src.config import settings
from src.core import Project
from src.paratranz import Paratranz


def main():
    project = Project()
    project.clean(
        settings.filepath.root / settings.filepath.converted,
        settings.filepath.root / settings.filepath.download,
        settings.filepath.root / settings.filepath.result,
        settings.filepath.root / settings.filepath.tmp,
    )
    # project.wash_encoding()
    project.convert()

    with httpx.Client() as client:
        paratranz = Paratranz(client=client)
        paratranz.download()

    project.restore()


if __name__ == '__main__':
    main()