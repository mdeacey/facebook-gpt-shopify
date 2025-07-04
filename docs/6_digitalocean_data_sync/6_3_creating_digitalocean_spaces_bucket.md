# Chapter 6: DigitalOcean Integration
## Subchapter 6.3: Creating a DigitalOcean Spaces Bucket

### Introduction
This subchapter guides you through creating a DigitalOcean Spaces bucket to store Facebook and Shopify data for the GPT Messenger sales bot. The bucket provides S3-compatible storage for persistent, scalable data management, replacing temporary file storage from Chapters 4–5. We configure the bucket and generate API credentials (`SPACES_API_KEY`, `SPACES_API_SECRET`) for use in Subchapters 6.1–6.2, organizing data by UUID (`users/<uuid>/...`) from `TokenStorage` (Chapter 3). The process is performed in the DigitalOcean control panel, ensuring compatibility with the FastAPI application running on a Droplet.

### Prerequisites
- Completed Chapters 1–5 and Subchapters 6.1–6.2.
- DigitalOcean account with access to the control panel.
- FastAPI application running on a DigitalOcean Droplet or locally.
- SQLite databases (`tokens.db`, `sessions.db`) set up (Chapter 3).

---

### Step 1: Access the DigitalOcean Control Panel
**Action**: Log into the DigitalOcean control panel at [cloud.digitalocean.com](https://cloud.digitalocean.com).

**Screenshot Reference**: Shows the DigitalOcean dashboard.

**Why?**
- The control panel manages Spaces, Droplets, and API credentials.
- Ensures you have access to create a bucket for the sales bot.

### Step 2: Navigate to Spaces
**Action**: In the left sidebar, click “Spaces” under “Manage”. If no Spaces exist, you’ll see a prompt to create one.

**Screenshot Reference**: Shows the “Spaces” section with a “Create Spaces” button.

**Why?**
- The “Spaces” section manages S3-compatible storage buckets.
- Creating a bucket enables persistent storage for Facebook and Shopify data.

### Step 3: Create a New Space
**Action**: Click the “Create Spaces” button. Configure the following:
- **Datacenter region**: Select `NYC3` (New York) or a region close to your Droplet for low latency.
- **Enable CDN**: Disable for simplicity (enable in production for performance).
- **Unique name**: Enter a unique name, e.g., `gpt-messenger-data