## 🔧 Facebook OAuth Setup

To enable Facebook OAuth in your application, you need to create a Facebook App and retrieve the following credentials:

- `FACEBOOK_APP_ID`
- `FACEBOOK_APP_SECRET`
- `FACEBOOK_REDIRECT_URI`

### 🛠️ Steps to Get Facebook OAuth Credentials

1. **Go to the Facebook Developer Console**  
   Visit [https://developers.facebook.com](https://developers.facebook.com) and log in with your Facebook account.

2. **Create a New App**

   - Click on **"My Apps"** in the top-right corner and select **"Create App"**
   - Choose **"Business"** or **"Consumer"** depending on your needs
   - Enter your **App Name**, **Contact Email**, and click **Create App**

3. **Add the Facebook Login Product**

   - After creating the app, go to the **"Add a Product"** section
   - Find **"Facebook Login"** and click **"Set Up"**
   - Choose **"Web"** as the platform
   - Enter `http://localhost:5000` as your **Site URL** (or your production URL later)

4. **Configure the Valid OAuth Redirect URI**

   - In the left sidebar, navigate to:  
     `Facebook Login` → `Settings`
   - In the **"Valid OAuth Redirect URIs"** field, enter:  
     ```
     http://localhost:5000/facebook/callback
     ```

5. **Get Your App ID and Secret**

   - In the left sidebar, go to:  
     `Settings` → `Basic`
   - Copy your:
     - `App ID` → use as `FACEBOOK_APP_ID`
     - `App Secret` → use as `FACEBOOK_APP_SECRET`

6. **Set Your Environment Variables**

   In your `.env` file (or your hosting environment), set the following:

   ```dotenv
   FACEBOOK_APP_ID=your_app_id
   FACEBOOK_APP_SECRET=your_app_secret
   FACEBOOK_REDIRECT_URI=http://localhost:5000/facebook/callback
