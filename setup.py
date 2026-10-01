from pathlib import Path

from setuptools import setup


project_root = Path(__file__).parent
requirements = [
    line.strip()
    for line in (project_root / "requirements.txt").read_text(encoding="utf-8").splitlines()
    if line.strip() and not line.lstrip().startswith("#")
]
long_description = (project_root / "README.md").read_text(encoding="utf-8")


setup(
    name="turso-korean-word-game",
    version="1.0.0",
    author="collt8080",
    url="https://github.com/collt8080/word-game",
    description="Turso 기반 Home Assistant 및 로컬 한국어 끝말잇기 게임",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=["turso_word_chain"],
    py_modules=["ha_word_relay", "word_store", "stdict_api", "jev_api"],
    install_requires=requirements,
    python_requires=">=3.10",
    project_urls={"Homepage": "https://github.com/collt8080/word-game"},
)