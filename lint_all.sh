echo "isort..."
isort .
echo "black..."
black .
echo "pylint..."
pylint -E $(pwd)
echo "flake8..."
flake8 --exclude .git,__pycache__,.venv --ignore E501
echo "mypy..."
mypy *.py
