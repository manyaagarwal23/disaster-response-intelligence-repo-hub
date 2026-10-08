## 🤖 AI review of changes vs `8c599c1`

20 file(s) reviewed with `qwen/qwen3.8-27b` on 2026-10-07. Advisory: a human still decides.

### 🔴 HIGH — `deploy/aws-cloudformation.yml`:88

**Issue:** The UserData script exports the Groq API key as a shell variable and passes it to the install script. If the install script (or any subprocess it spawns) does not explicitly sanitize the environment, the secret may be leaked into logs, crash reports, or child processes that inherit the environment.

**Suggested fix:** Pass the secret via a temporary file with strict permissions (e.g., `mktemp`, `chmod 600`) or use AWS Secrets Manager/SSM Parameter Store with restricted access, rather than exporting it as a shell variable in UserData.

### 🔴 HIGH — `rag/llm.py`:135

**Issue:** The `LLMClient` class is not thread-safe. The `self.dead` set and `self.clients` list are mutated without locks, but the client is shared across threads (via `get_llm` in a web server context). This can lead to race conditions where a key is marked dead concurrently or a client is initialized twice, potentially causing inconsistent state or crashes.

**Suggested fix:** Add a `threading.Lock` to `LLMClient` and acquire it in `_client` and `_try_keys` when modifying `self.clients` or `self.dead`.

### 🔴 HIGH — `reports/session-2026-10-07/scripts/ff_ui.py`:8

**Issue:** Hardcoded absolute paths for Firefox and geckodriver (`/snap/...`) will cause the script to crash on any system not using the specific Snap installation, breaking the test suite in other environments.

**Suggested fix:** Use `shutil.which('firefox')` and `shutil.which('geckodriver')` to locate binaries dynamically, or allow configuration via environment variables.

### 🔴 HIGH — `reports/session-2026-10-07/scripts/slides_v4.py`:5

**Issue:** Hardcoded absolute path to a local user's home directory will cause the script to fail on any other machine or CI environment.

**Suggested fix:** Accept the source file path as a command-line argument or environment variable instead of hardcoding it.

### 🔴 HIGH — `reports/session-2026-10-07/scripts/slides_v4.py`:10

**Issue:** The script assumes the 10th slide (index 9) exists and contains a picture shape; if the deck structure changes or the slide is missing, it will crash with an IndexError or StopIteration.

**Suggested fix:** Add checks to verify the slide exists and that a picture shape is found before proceeding, exiting with a clear error message if not.

### 🟠 MEDIUM — `deploy/aws-cloudformation.yml`:92

**Issue:** The script uses `set -euo pipefail` but does not handle the case where `git clone` fails (e.g., network error, invalid branch). The script will exit silently without logging the specific error to a persistent location, making debugging difficult in a disaster response scenario.

**Suggested fix:** Add explicit error handling around `git clone` to log the failure to `/var/log/rag-install.log` before exiting, or use a `trap` to capture and log errors.

### 🟠 MEDIUM — `rag/generator.py`:219

**Issue:** The code checks `llm_module.last_provider()` to determine if the local Ollama model was used. If `last_provider()` is not thread-safe or if the LLM call fails and falls back to a different provider without updating this state, the logic may incorrectly route the response to `local_answer()` or `parse_answer()`, leading to malformed responses or crashes.

**Suggested fix:** Ensure `last_provider()` is thread-safe (e.g., using a thread-local storage or atomic variable) and that it is reliably updated after every LLM invocation, including fallbacks.

### 🟠 MEDIUM — `rag/llm.py`:142

**Issue:** The `complete` method uses `time.sleep` to wait for rate limits. In a multi-threaded web server, this blocks the worker thread, reducing concurrency and potentially causing timeouts for other users if many requests hit rate limits simultaneously.

**Suggested fix:** Consider using an asynchronous sleep or a non-blocking retry mechanism if the web framework supports it, or ensure the web server has sufficient worker threads to handle blocking waits.

### 🟠 MEDIUM — `reports/session-2026-10-07/scripts/ff_ui.py`:15

**Issue:** The script assumes the application is running at `http://localhost:8080` without any configuration option, which will fail if the service is running on a different port or host.

**Suggested fix:** Accept the base URL as a command-line argument or environment variable (e.g., `BASE_URL`).

### 🟠 MEDIUM — `reports/session-2026-10-07/scripts/rank_probe.py`:3

**Issue:** Hardcoded path `/app/rag` for `sys.path` and data files will cause `ImportError` or `FileNotFoundError` if the repository is not mounted at `/app`.

**Suggested fix:** Use relative paths based on the script's location or environment variables to locate the `rag` module and data files.

### 🟠 MEDIUM — `reports/session-2026-10-07/scripts/recall_probe.py`:3

**Issue:** Hardcoded path `/app/rag` for `sys.path` and data files will cause `ImportError` or `FileNotFoundError` if the repository is not mounted at `/app`.

**Suggested fix:** Use relative paths based on the script's location or environment variables to locate the `rag` module and data files.

### 🟠 MEDIUM — `reports/session-2026-10-07/scripts/score_experiment.py`:3

**Issue:** Hardcoded path `/app/rag` for `sys.path` and data files will cause `ImportError` or `FileNotFoundError` if the repository is not mounted at `/app`.

**Suggested fix:** Use relative paths based on the script's location or environment variables to locate the `rag` module and data files.

### 🟠 MEDIUM — `reports/session-2026-10-07/scripts/slides_v4.py`:14

**Issue:** Opening the image file with PIL does not validate that it is a valid image or handle corrupted files, which can lead to unhandled exceptions.

**Suggested fix:** Wrap the image opening and size retrieval in a try-except block to handle IOError or PIL.UnidentifiedImageError gracefully.

### 🟡 LOW — `rag/generator.py`:168

**Issue:** The `looks_degenerate` function uses a hardcoded threshold for non-Latin characters (`ord(c) > 0x24F`). This may incorrectly flag valid non-English text (e.g., Cyrillic, Greek, or CJK characters) as degenerate, causing valid answers to be rejected.

**Suggested fix:** Use a more robust check for 'junk' text, such as checking for a high ratio of control characters or specific known junk patterns, rather than a broad Unicode range check.

### 🟡 LOW — `rag/llm.py`:105

**Issue:** The `ollama_complete` function uses `urllib.request` which is synchronous and can block for a long time (minutes) on CPU-bound local models. This is acceptable as a fallback but should be documented clearly to avoid unexpected latency in production if the fallback is triggered frequently.

**Suggested fix:** Ensure the UI or API client handles long timeouts gracefully and consider adding a progress indicator or timeout message for local model calls.

### 🟡 LOW — `reports/session-2026-10-07/scripts/cssdiag.py`:5

**Issue:** Hardcoded absolute paths for Firefox and geckodriver (e.g., /snap/firefox/...) will cause the script to fail on systems where these binaries are installed in different locations (e.g., standard Linux package managers or Windows).

**Suggested fix:** Use environment variables or standard PATH resolution to locate the browser and driver binaries instead of hardcoding absolute paths.

### 🟡 LOW — `reports/session-2026-10-07/scripts/diag.py`:5

**Issue:** Hardcoded absolute paths for Firefox and geckodriver will cause the script to fail on systems where these binaries are installed in different locations.

**Suggested fix:** Use environment variables or standard PATH resolution to locate the browser and driver binaries instead of hardcoding absolute paths.


---

## Decisions (human triage, 2026-10-07)

| Finding | Decision |
|---|---|
| HIGH `aws-cloudformation.yml`: key exported in user data | **Fixed.** The key(s) now live in a Secrets Manager secret created by the stack; an instance role may read it and user data fetches it at boot. Nothing secret is in user data any more. |
| HIGH `llm.py`: `LLMClient` not thread-safe | **Not a bug as described**: `get_llm()` builds a new client per request, so no client is shared between threads. The real gap behind it was fixed: rejected keys are now remembered process-wide (`_DEAD_KEYS`, lock-guarded), as the docstring promised. |
| HIGH `ff_ui.py`: hard-coded Firefox/geckodriver paths | **Fixed**: `BASE_URL`, `FIREFOX_BIN`, `GECKODRIVER` environment overrides. |
| HIGH `slides_v4.py` (×2): hard-coded paths, no checks | **Not applied**: a saved record of a one-off run in `reports/session-2026-10-07/`, and no further slide work is wanted. |
| MEDIUM user data: `git clone` failure not logged | **Fixed**: all of user data now logs to `/var/log/rag-install.log` with an ERR trap. |
| MEDIUM `generator.py`: `last_provider()` thread safety | **Already thread-local** (`threading.local()`); set after every completion including the local fallback. |
| MEDIUM `llm.py`: `time.sleep` blocks a worker | **Accepted**: waits are bounded (≤ 10 s, one pass) and the server runs sync endpoints in a thread pool. |
| MEDIUM `ff_ui.py`: base URL hard-coded | **Fixed** (see above). |
| MEDIUM probes: `/app/rag` paths | **Not applied**: documented as container-only one-off scripts. |
| MEDIUM `slides_v4.py`: PIL error handling | **Not applied** (see above). |
| LOW `looks_degenerate`: non-Latin threshold | **Kept, documented**: answers are expected in English; a mostly non-Latin reply is junk on purpose. |
| LOW `ollama_complete` blocks for minutes | **Documented** in README and the API note on local answers. |
| LOW diag scripts: hard-coded paths | **Not applied**: one-off records. |
