.PHONY: demo live test fresh

demo:
	python main.py --mode demo

live:
	python main.py

fresh:
	python main.py --refresh

test:
	python -m pytest -q
