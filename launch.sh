SCRIPT_DIR="$( cd "$( dirname "$(readlink -f "${BASH_SOURCE[0]}")" )" && pwd )"

# Activate the virtual environment and run the app using absolute paths
source "$SCRIPT_DIR/shellyenv/bin/activate"
python3 "$SCRIPT_DIR/my_app.py" "$@"
