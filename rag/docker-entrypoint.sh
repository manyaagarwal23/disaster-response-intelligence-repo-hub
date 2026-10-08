#!/bin/sh
# Container start-up: make sure the vector database exists before
# serving. Only runs for the web server command, so one-off commands
# like "docker run <image> pytest" are not affected.
set -e

if [ "$1" = "uvicorn" ] && [ ! -f "$CHROMA_PATH/chroma.sqlite3" ]; then

    if [ ! -d "$USHAHIDI_PATH/.git" ]; then
        COMMIT=$(python -c "import config; print(config.USHAHIDI_COMMIT)")
        URL=$(python -c "import config; print(config.USHAHIDI_REPO_URL)")

        echo "Fetching Ushahidi $COMMIT into $USHAHIDI_PATH ..."
        git init -q "$USHAHIDI_PATH"
        git -C "$USHAHIDI_PATH" remote add origin "$URL"
        git -C "$USHAHIDI_PATH" fetch -q --depth 1 origin "$COMMIT"
        git -C "$USHAHIDI_PATH" checkout -q FETCH_HEAD
    fi

    echo "Building vector database (first start only) ..."
    python ingestion.py
fi

exec "$@"
