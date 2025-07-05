# Chapter 8: Advanced Agent Deployment
## Subchapter 8.1: Creating an AI Agent on DigitalOcean

### Introduction
This subchapter guides you through creating an AI agent on DigitalOcean’s GenAI Platform to enhance the GPT Messenger sales bot with advanced capabilities. The agent leverages the Llama 3.3 Instruct model for domain-specific tasks, integrating with the previously created workspace and Spaces bucket from Chapters 6–7. The process involves configuring the agent with instructions and deploying it within the DigitalOcean control panel, ensuring seamless integration with the FastAPI application.

### Prerequisites
- Completed Chapters 1–7 and Subchapters 8.1–8.2.
- DigitalOcean account with access to the GenAI Platform.
- Workspace `facebook-gpt-shopfiy-agents` and Spaces bucket `shopify-genai-data` set up (Chapter 6).
- FastAPI application running on a DigitalOcean Droplet or locally.

---

### Step 1: Access the DigitalOcean Control Panel
**Action**: Log into the DigitalOcean control panel at [cloud.digitalocean.com](https://cloud.digitalocean.com).

**Screenshot Reference**: Shows the DigitalOcean dashboard.

**Why?**
- The control panel manages the GenAI Platform and agent creation.
- Ensures you have access to deploy an AI agent for the sales bot.

### Step 2: Navigate to GenAI Platform
**Action**: In the left sidebar, click “GenAI Platform” under “Manage” and select “New” to start the agent creation process.

**Screenshot Reference**: Shows the “GenAI Platform” section with a “New” option.

**Why?**
- The GenAI Platform hosts AI agent development and deployment.
- Initiates the creation of a new agent for the sales bot.

### Step 3: Create a New Workspace
**Action**: Choose “Create New” workspace, then configure the following:
- **Workspace name**: Enter `facebook-gpt-shopfiy-agents`.
- **Workspace description**: Provide a short description, e.g., “Workspace for managing Facebook and Shopify sales bot agents.”

**Screenshot Reference**: Shows the workspace creation form with fields filled.

**Why?**
- A workspace organizes agents and provides a dedicated environment.
- Helps group agents related to the sales bot for better management.

### Step 4: Configure the Agent
**Action**: Click “Create” to proceed, then configure the agent:
- **Agent name**: Enter `facebook-gpt-shopfiy-agent`.
- **Agent instructions**: Provide instructions, e.g., “Assist users with Facebook and Shopify sales inquiries, using data from the shopify-genai-data bucket.”
- **Select a model**: Choose Llama 3.3 Instruct (70B) with $0.65000/1M input tokens and $0.65000/1M output tokens.

**Screenshot Reference**: Shows the agent configuration form with fields filled.

**Why?**
- Defines the agent’s role and expertise for sales support.
- Ensures the model aligns with the agent’s intended use case.

### Step 5: Deploy the Agent
**Action**: Click “Create Agent” to initiate deployment. Monitor the deployment progress.

**Screenshot Reference**: Shows the deployment in progress banner.

**Why?**
- Deploys the agent for use with the sales bot.
- Allows testing and integration with the FastAPI application.

---