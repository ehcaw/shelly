# Directory where the script is located
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

# Install dependencies
echo "Installing dependencies..."
pip install -e .

# Create wrapper script
WRAPPER_SCRIPT="$SCRIPT_DIR/$ENV_NAME/bin/your-command-name"
cat > "$WRAPPER_SCRIPT" << EOL
#!/bin/bash
source "$SCRIPT_DIR/$ENV_NAME/bin/activate"
python "$SCRIPT_DIR/your_main_script.py" "\$@"
EOL

chmod +x "$WRAPPER_SCRIPT"

# Add to PATH
# First, determine the shell configuration file
SHELL_CONFIG=""
if [ -n "$ZSH_VERSION" ]; then
    SHELL_CONFIG="$HOME/.zshrc"
elif [ -n "$BASH_VERSION" ]; then
    SHELL_CONFIG="$HOME/.bashrc"
else
    echo "Unsupported shell"
    exit 1
fi

# Add PATH update to shell configuration if not already present
if ! grep -q "$SCRIPT_DIR/$ENV_NAME/bin" "$SHELL_CONFIG"; then
    echo "export PATH=\"$SCRIPT_DIR/$ENV_NAME/bin:\$PATH\"" >> "$SHELL_CONFIG"
    echo "Added command to PATH in $SHELL_CONFIG"
fi

chmod +x launch.sh

ln -s "$SCRIPT_DIR/launch.sh" /usr/local/bin/shelly

cp install.sh /usr/local/bin/shelly
chmod +x /usr/local/bin/shelly

export PATH="/path/to/script/directory:$PATH"

echo "Installation complete!"
echo "Please restart your terminal or run: source $SHELL_CONFIG"
