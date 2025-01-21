set -e
echo "🚀 Running some setup commands..."

echo "Installing tmux!"
brew install tmux

echo "Creating virtual environment..."
python3 -m venv zapenv

echo "Downloading dependencies..."
pip install -r requirements.txt

echo "Installing repomix..."
npm install -g repomix

echo "Installing ollama embedding model"
ollama pull nomic-embed-text

echo "Setup complete!"
