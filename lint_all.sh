echo "isort..."
isort
echo "black..."
black .
echo "pylint..."
pylint -E $(pwd);
echo "flake8..."
flake8
echo "mypy..."
mypy *.py
