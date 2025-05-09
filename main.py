import httpx

from src import Paratranz
from src.core import Project


def main():
    project = Project()
    project.convert()

    with httpx.Client() as client:
        paratranz = Paratranz(client=client)
        paratranz.download()

    project.restore()


if __name__ == '__main__':
    main()