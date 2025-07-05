# Chapter 8: Advanced Agent Deployment
## Subchapter 8.2: Configuring Agent Access Keys on DigitalOcean

### Introduction
This subchapter guides you through setting up an AI agent on DigitalOcean’s GenAI Platform and configuring access keys to enable secure integration with the GPT Messenger sales bot. The process includes deploying the agent with the Llama 3.3 Instruct model and generating endpoint access keys for use with the FastAPI application, building on the workspace and Spaces bucket established in previous chapters.

### Prerequisites
- Completed Chapters 1–7 and Subchapter 8.1.
- DigitalOcean account with access to the GenAI Platform.
- Workspace `facebook-gpt-shopfiy-agents` and Spaces bucket `shopify-genai-data` set up (Chapter 6).
- FastAPI application running on a DigitalOcean Droplet or locally.

---

### Step 1: Access the DigitalOcean Control Panel
**Action**: Log into the DigitalOcean control panel at [cloud.digitalocean.com](https://cloud.digitalocean.com).

**Screenshot Reference**: Shows the DigitalOcean dashboard.

**Why?**
- The control panel manages the GenAI Platform and agent deployment.
- Ensures you have access to configure and deploy the agent.

### Step 2: Navigate to GenAI Platform
**Action**: In the left sidebar, click “GenAI Platform” under “Manage” and select “New” to start the agent creation process.

**Screenshot Reference**: Shows the “GenAI Platform” section with a “New” option.

**Why?**
- The GenAI Platform hosts AI agent development and deployment.
- Initiates the creation of a new agent for the sales bot.

### Step 3: Create a New Agent
**Action**: Choose “Create New” workspace if not already created, then configure the agent:
- **Workspace name**: Enter `facebook-gpt-shopfiy-agents`.
- **Agent name**: Enter `facebook-gpt-shopfiy-agent`.
- **Agent instructions**: Provide instructions, e.g., “Assist users with Facebook and Shopify sales inquiries, using data from the shopify-genai-data bucket.”
- **Select a model**: Choose Llama 3.3 Instruct (70B) with $0.65000/1M input tokens and $0.65000/1M output tokens.
- Click “Create Agent” to initiate deployment.

**Screenshot Reference**: Shows the agent configuration form and deployment in progress banner.

**Why?**
- Sets up a dedicated agent for sales support within the workspace.
- Deploys the agent for use with the sales bot.

### Step 4: Monitor Deployment
**Action**: Wait for the deployment to complete. The “Agent deployment in progress...” banner will dismiss once finished.

**Screenshot Reference**: Shows the deployment in progress banner.

**Why?**
- Ensures the agent is fully deployed before proceeding.
- Allows time for the system to configure the agent environment.

### Step 5: Create Agent Access Key
**Action**: Navigate to the agent settings, click “Create Key” under “Endpoint Access Keys”, and configure:
- **Key name**: Enter `facebook-gpt-shopfiy-agent`.
- Copy the generated secret key (e.g., `1XxJxhVp4F3z0ejVF_NDrTKd8QYMUJL3`) immediately, as it won’t be shown again.

**Screenshot Reference**: Shows the “Create Agent Access Key” popup and the key generation confirmation.

**Why?**
- Generates secure access keys for the agent endpoint.
- Enables the FastAPI application to authenticate and interact with the agent.

---