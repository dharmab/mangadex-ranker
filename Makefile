.PHONY: default help ci check-style check-type

default: help

help:
	./mangadex.py -h

ci: check-style check-type

check-style:
	flake8 \
	  --ignore=E501 \
	  mangadex.py

check-type:
	mypy mangadex.py
