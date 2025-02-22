SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Environment name
ENV_NAME="shellyenv"

# Check if virtual environment exists, create if it doesn't
if [ ! -d "$SCRIPT_DIR/$ENV_NAME" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$SCRIPT_DIR/$ENV_NAME"
fi

# Activate virtual environment
source "$SCRIPT_DIR/$ENV_NAME/bin/activate"

# Install requirements if requirements.txt exists
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    echo "Installing requirements..."
    pip install -r "$SCRIPT_DIR/requirements.txt"
else
    echo "No requirements.txt found, skipping package installation"
fi

# Create symbolic link for the launch script
if [ ! -f "/usr/local/bin/shelly" ]; then
    echo "Creating shelly command..."
    sudo ln -s "$SCRIPT_DIR/launch.sh" /usr/local/bin/shelly
    sudo chmod +x /usr/local/bin/shelly
fi

echo "Installation complete!"
echo "You can now use the 'shelly' command from anywhere"
```

And keep your `launch.sh` simple:
```bash
#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Activate the virtual environment and run the app
source "$SCRIPT_DIR/shellyenv/bin/activate"
python3 "$SCRIPT_DIR/my_app.py" "$@"
