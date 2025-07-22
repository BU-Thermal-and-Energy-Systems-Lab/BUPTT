#!/usr/bin/env bash
set -euo pipefail

# --- CONFIG ---------------------------------------------------------------
YAML_FILE="environment.yml"          # your environment file
SCRIPT_TO_RUN="main.py"              # the Python entrypoint you want to launch
SHORTCUT_NAME="BUPTT"                # name of the clickable shortcut
ENV_NAME=""                          # leave empty to read from YAML

# --- FUNCTIONS ------------------------------------------------------------
get_env_name() {
  # Read 'name:' from YAML if ENV_NAME not set
  if [[ -z "$ENV_NAME" ]]; then
    ENV_NAME=$(grep -E '^name:' "$YAML_FILE" | head -1 | awk '{print $2}')
    if [[ -z "$ENV_NAME" ]]; then
      echo "Could not parse environment name from $YAML_FILE" >&2
      exit 1
    fi
  fi
}

create_or_update_env() {
  echo "Creating/updating conda environment '$ENV_NAME' from $YAML_FILE ..."
  # Use conda in a login shell context
  eval "$(/usr/bin/conda shell.bash hook 2>/dev/null || conda shell.bash hook 2>/dev/null || true)"
  if conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
    echo "Environment exists; updating..."
    conda env update -n "$ENV_NAME" -f "$YAML_FILE" --prune
  else
    echo "Environment does not exist; creating..."
    conda env create -f "$YAML_FILE"
  fi
}

make_shortcut() {
  local desktop="$HOME/Desktop"
  local shortcut_path="$desktop/$SHORTCUT_NAME"

  echo "Generating shortcut at: $shortcut_path"

  # Resolve conda base to correctly activate
  local conda_base
  conda_base=$(conda info --base)

  cat > "$shortcut_path" <<EOF
#!/usr/bin/env bash
# Auto-generated launcher for $SCRIPT_TO_RUN inside $ENV_NAME

# Load conda
source "$conda_base/etc/profile.d/conda.sh"
conda activate "$ENV_NAME"

# Run script (adjust path if needed)
python "$(pwd)/$SCRIPT_TO_RUN"
EOF

  chmod +x "$shortcut_path"
  echo "Done. Double-click '$SHORTCUT_NAME' on your Desktop to run the app."
}

# --- MAIN -----------------------------------------------------------------
if [[ ! -f "$YAML_FILE" ]]; then
  echo "Missing $YAML_FILE in current directory." >&2
  exit 1
fi
if [[ ! -f "$SCRIPT_TO_RUN" ]]; then
  echo "Missing $SCRIPT_TO_RUN in current directory." >&2
  exit 1
fi

get_env_name
create_or_update_env
make_shortcut
