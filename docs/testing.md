# Running the test suite

1. Ensure you have [`uv`](https://github.com/astral-sh/uv) installed.
2. Create a virtual environment and install dependencies:

   ```bash
   uv venv
   source .venv/bin/activate
   uv pip install -e . openai pytest python-dotenv
   ```

3. Add a `.env` file inside the `tests/` directory with values for at least `AICM_API_KEY` and any provider keys you plan to test (for example `OPENAI_API_KEY`).  Without a valid `AICM_API_KEY` the tracking wrapper cannot deliver usage data.

4. Run `pytest` to execute the suite.
