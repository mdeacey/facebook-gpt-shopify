## 8.5 Testing the GenAI Integration

This subchapter outlines the testing procedures for the GenAI integration implemented in Subchapters 8.1 through 8.4. It ensures the prompt, agent logic, webhook, and environment variables work together to process incoming Facebook messages, generate AI responses, and store them correctly in DigitalOcean Spaces. The testing format aligns with previous testing subchapters, providing structured steps and expected outcomes.

### Overview
Testing verifies that:
- The AI prompt is correctly loaded and formatted.
- The GenAI agent retrieves data, generates responses, and sends them via the Facebook Messenger API.
- The webhook stores incoming messages and AI responses in Spaces.
- Environment variables are properly validated.
- Error handling manages failures gracefully.

### Testing Steps
1. **Test Prompt Loading**:
   - **Action**: Ensure `digitalocean_integration/prompt.txt` exists with the correct placeholders.
   - **Verification**: Run the application and check logs to confirm `prompt.txt` is read without errors.
   - **Expected Outcome**: No `FileNotFoundError` in logs; the prompt is loaded successfully.

2. **Test Data Retrieval**:
   - **Action**: Simulate data in Spaces for `users/<uuid>/shopify/shop_metadata.json`, `users/<uuid>/shopify/shop_products.json`, `users/<uuid>/facebook/<page_id>/page_metadata.json`, and `users/<uuid>/facebook/<page_id>/conversations/<sender_id>.json`.
   - **Verification**: Call `get_data_from_spaces` with mock keys and verify it returns data or an empty list for non-existent conversation files.
   - **Expected Outcome**: Data is retrieved correctly, or an empty list is returned for new conversations.

3. **Test GenAI Response Generation**:
   - **Action**: Send a test request to the GenAI API using a mock prompt and the `GENAI_API_KEY`.
   - **Verification**: Use a tool like Postman to call the endpoint specified in `GENAI_ENDPOINT` with a sample prompt.
   - **Expected Outcome**: The API returns a 200 response with a generated text output.

4. **Test Message Sending**:
   - **Action**: Use a mock Facebook access token to call `send_facebook_message` with a test message.
   - **Verification**: Check the response from the Facebook Messenger API.
   - **Expected Outcome**: The message is sent successfully, and a message ID is returned.

5. **Test Webhook Processing**:
   - **Action**: Send a test message to the `/facebook/webhook` endpoint using a tool like `curl` or the Facebook Messenger API:
     ```bash
     curl -X POST http://localhost:5000/facebook/webhook \
       -H "Content-Type: application/json" \
       -H "X-Hub-Signature: sha1=<hmac_signature>" \
       -d '{"object":"page","entry":[{"id":"page_id","messaging":[{"sender":{"id":"sender_id"},"recipient":{"id":"page_id"},"timestamp":1697051234567,"message":{"mid":"test_mid","text":"Hello"}}]}]}'
     ```
   - **Verification**: Check Spaces for the conversation file `users/<uuid>/facebook/<page_id>/conversations/<sender_id>.json` and verify the incoming message and AI response are stored.
   - **Expected Outcome**: The message is stored, an AI response is generated and sent, and both are appended to the conversation file with the correct payload format (`sender`, `recipient`, `timestamp`, `message`).

6. **Test Environment Variable Validation**:
   - **Action**: Start the application without `GENAI_API_KEY` in the `.env` file.
   - **Verification**: Check if the application fails to start with an error listing missing variables.
   - **Expected Outcome**: The application fails gracefully, reporting the missing `GENAI_API_KEY`.

7. **Test Error Handling**:
   - **Action**: Simulate failures:
     - Remove `prompt.txt` to trigger a `FileNotFoundError`.
     - Use an invalid `GENAI_API_KEY` to trigger an API failure.
     - Send an invalid message payload to the webhook (e.g., missing `text`).
   - **Verification**: Check logs for appropriate error messages and HTTP 500 responses.
   - **Expected Outcome**: Errors are logged, and HTTP 500 errors are raised for API and file issues; invalid payloads are skipped gracefully.

### Expected Outcomes
- The prompt is loaded and formatted correctly.
- Data is retrieved from Spaces or initialized as an empty list for new conversations.
- The GenAI API generates valid responses.
- Messages are sent via the Facebook Messenger API and stored in Spaces.
- Environment variables are validated at startup.
- Errors are handled with appropriate logging and HTTP responses.

### Notes
- **Prerequisites**: Complete Subchapters 8.1 through 8.4 to ensure all components (prompt, agent, webhook, environment) are implemented.
- **Future Enhancements**: Consider adding retry logic for API failures or default responses for fallback scenarios in a future subchapter (e.g., 8.6).
- This testing approach aligns with previous chapters, focusing on structured steps and clear verification criteria.