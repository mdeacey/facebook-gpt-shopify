## 8.4 Setting Up the DigitalOcean GenAI Agent

This subchapter covers configuring the DigitalOcean GenAI agent using the DigitalOcean user interface (UI) to obtain the API key and set up the endpoint for use in the GPT Messenger sales bot. This configuration enables the agent to generate responses for incoming Facebook messages.

### Overview
The DigitalOcean GenAI agent requires an API key and an endpoint URL, which are used in `digitalocean_integration/agent.py` to make API calls. This subchapter guides you through creating an API key and configuring the GenAI model in the DigitalOcean UI, ensuring the agent is ready for integration with the webhook (Subchapter 8.3).

### Implementation Details
1. **Access the DigitalOcean Dashboard**:
   - Log in to your DigitalOcean account at `https://cloud.digitalocean.com`.
   - Navigate to the “API” section under “Manage” in the left sidebar.

2. **Generate an API Key**:
   - Click “Generate New Token” in the API section.
   - Name the token (e.g., “GPTMessengerGenAI”).
   - Set the scope to include access to AI services (select relevant permissions if prompted).
   - Copy the generated API key and store it securely.

3. **Configure the GenAI Model**:
   - Navigate to the AI or GenAI section of the DigitalOcean dashboard (exact location may vary based on UI updates).
   - Select the Llama 3.3 70B Instruct model (or the desired model, matching the `model` parameter in `agent.py`).
   - Note the API endpoint URL provided (e.g., `https://api.genai.digitalocean.com/v1/llama3.3-70b-instruct`).
   - If no specific endpoint is provided, use the default endpoint specified in `agent.py`.

4. **Update Environment Variables**:
   - Add the API key to your `.env` file as `GENAI_API_KEY`.
   - Optionally, add the endpoint as `GENAI_ENDPOINT` if different from the default.

**Example `.env` Entries**:
```
GENAI_API_KEY=your_genai_api_key
GENAI_ENDPOINT=https://api.genai.digitalocean.com/v1/llama3.3-70b-instruct
```

### Testing
1. **Verify API Key**: Add the `GENAI_API_KEY` to your `.env` file and restart the application to ensure it starts without errors.
2. **Test Endpoint Accessibility**: Use a tool like `curl` or Postman to send a test request to the GenAI endpoint with the API key:
   ```bash
   curl -X POST https://api.genai.digitalocean.com/v1/llama3.3-70b-instruct \
     -H "Authorization: Bearer your_genai_api_key" \
     -H "Content-Type: application/json" \
     -d '{"model": "llama3.3-70b-instruct", "prompt": "Test prompt", "max_tokens": 10}'
   ```
3. **Expected Outcome**: The API should return a 200 response with a generated text output. If the response is non-200, verify the API key and endpoint in the DigitalOcean UI.

### Notes
- **Security**: Store the API key securely and avoid committing it to version control.
- **Model Selection**: Ensure the selected model matches the `model` parameter in `agent.py` (`llama3.3-70b-instruct`).
- **Prerequisite**: This subchapter should be completed before testing the full integration in Subchapter 8.5.
- If the DigitalOcean UI changes, consult the official DigitalOcean documentation for updated steps to generate API keys and configure AI models.