## 🍴 Fork & Setup

Want to run your own instance of musiccc? Follow these steps!

1. **Fork** this repository to your GitHub account.
2. Clone your fork:

   ```bash
   git clone YOUR_FORK_URL
   cd musiccc
   ```

3. Install the required dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the root folder.

5. Add your own API keys and credentials:

   ```env
   DISCORD_TOKEN=your_discord_bot_token
   SPOTIFY_CLIENT_ID=your_spotify_client_id
   SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
   ```

6. Start the bot:

   ```bash
   python main.py
   ```

### 🔑 Required API Keys

Each user must provide their own credentials.

| API | Where to get it |
|---|---|
| Discord Bot Token | [Discord Developer Portal](https://discord.com/developers/applications) |
| Spotify Client ID | [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) |
| Spotify Client Secret | [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) |

**Important:**
- Never share your API keys or bot token.
- Never commit your `.env` file.
- Each fork must use its own credentials.
- Do not use the original developer's API keys.
