# disco-robo
Discord robot for organizing ultimate frisbee games and tracking attendance.

## Overview
disco-robo is a Discord bot that helps manage ultimate frisbee teams by:
- Managing team rosters and player information
- Scheduling games and sending automatic reminders
- Tracking player attendance through Discord reactions
- Sending escalating reminders (initial announcement → bother → pester → day-of)

## To use
This bot is designed to run in user mode on a Raspberry Pi or any system with Python 3.7+. The database is STORED LOCALLY and must be configured to be backed up or risk data loss!

**⚠️ WARNING: Raspberry Pi SD Cards are not reliable as storage media!! They are a KNOWN FAILURE RISK! Set up regular backups!**

### 1. Initial Setup

#### a) Cloning the repo
Clone the repo with the url above, or fork into your own account:
```bash
git clone https://github.com/nevelo/disco-robo.git
cd disco-robo
```

#### b) Setting up the virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

#### c) Connecting to your Discord server

##### Creating a Discord Bot
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to the "Bot" section and click "Add Bot"
4. Under "Privileged Gateway Intents", enable:
   - Server Members Intent
   - Message Content Intent
5. Copy the bot token (you'll need this for config.json)

##### Inviting the Bot to Your Server
1. Go to OAuth2 → URL Generator
2. Select scopes: `bot`
3. Select bot permissions:
   - Read Messages/View Channels
   - Send Messages
   - Add Reactions
   - Read Message History
4. Copy the generated URL and open it in your browser to invite the bot

##### Writing your config/config.json file
On first run, the bot will create a default `config/config.json` file. Edit it with your settings:

```json
{
    "discord_token": "YOUR_BOT_TOKEN_HERE",
    "database_url": "db/disco_robo.db",
    "logfile": "logs/disco_robo.log",
    "tracked_teams": [],
    "privileged_users": [123456789012345678],
    "timezone": "America/Toronto",
    "channels": {
        "announcements": 123456789012345678,
        "bot_commands": 123456789012345678
    }
}
```

**Configuration fields:**
- `discord_token`: Your bot token from Discord Developer Portal
- `database_url`: Path to SQLite database (or MySQL/PostgreSQL connection string)
- `logfile`: Path where bot logs will be written
- `tracked_teams`: List of team IDs that this bot instance will track (add these after creating teams)
- `privileged_users`: List of Discord user IDs who can use admin commands
- `timezone`: Timezone for game scheduling (e.g., "America/Toronto", "America/New_York")
- `channels`:
  - `announcements`: Channel ID where game announcements will be posted
  - `bot_commands`: Channel ID for bot status messages

##### Getting Channel IDs
1. Enable Developer Mode in Discord (User Settings → Advanced → Developer Mode)
2. Right-click on a channel and select "Copy ID"
3. Paste the ID into your config.json

##### Getting Your Discord User ID
Right-click on your username in Discord and select "Copy ID". Add this to the `privileged_users` array in config.json.

#### d) Running the bot
```bash
python disco-robo.py
```

The bot will start and connect to Discord. You should see "I'm... alive!" in your bot_commands channel.

### 2. Building your database

All commands require privileged user permissions and use the format `!command param1=value1 param2="value with spaces"`.

#### a) Creating teams
```
!create_team name="Team Name" year=2025 season="Spring" home_colour="blue" away_colour="white"
```

**Parameters:**
- `name`: Team name (required)
- `year`: Year (required, must be current year or later)
- `season`: Season name like "Spring", "Summer", "Fall", "Winter" (required)
- `home_colour`: Home jersey colour (optional, default: white)
- `away_colour`: Away jersey colour (optional, default: black)

**Available colours:** black, white, green, blue, yellow, orange, brown, red, purple, pink, rainbow

**Example:**
```
!create_team name="Maverick" year=2025 season="Spring League" home_colour="white" away_colour="blue"
```

The bot will respond with the team ID. **Save this ID** - you'll need it for tracking and adding players/games.

#### b) Creating players
```
!create_player first="FirstName" last="LastName" gender=f discord="username"
```

**Parameters:**
- `first`: Player's first name (required)
- `last`: Player's last name (required)
- `gender`: Gender matching - `m` or `o` for open matching, `f` for female matching (required)
- `discord`: Discord username or ID (optional but recommended for attendance tracking)

**Example:**
```
!create_player first="Jane" last="Smith" gender=f discord="janesmith"
```

The bot will respond with the player ID and confirm Discord linking if found.

#### c) Adding players to teams
```
!add_player player=PLAYER_ID team=TEAM_ID
```

**Example:**
```
!add_player player=5 team=1
```

#### d) Adding games to teams
```
!create_game away=AWAY_TEAM_ID home=HOME_TEAM_ID date="YYYY-MM-DD" time="HH:MM" park="Park Name" field=1
```

**Parameters:**
- `away`: Away team ID (required)
- `home`: Home team ID (required)
- `date`: Game date in YYYY-MM-DD format (required)
- `time`: Game time in 24-hour format HH:MM (required)
- `park`: Park/facility name (required)
- `field`: Field number (required)

**Example:**
```
!create_game away=1 home=2 date="2025-06-15" time="19:00" park="Margaret Greene" field=3
```

#### e) Tracking teams
After creating a team, tell the bot to track it for announcements:
```
!track TEAM_ID
```

This adds the team to your config.json's `tracked_teams` list.

### 3. Game reminders

The bot automatically sends game reminders through the `check_messages` task that runs every hour. Once a game is created for a tracked team, the bot will:

1. **Initial Announcement (3 days before)**: Posts game details with 👍/👎 reactions for attendance
2. **Bother Message (2 days before)**: Mentions players who haven't responded
3. **Pester Message (1 day before)**: Urgent reminder for pending players
4. **Day-of Reminder (game day after 8 AM)**: Final attendance status

All messages are posted to the `announcements` channel configured in config.json.

### 4. Attendance tracking

Attendance tracking is fully automated through Discord reactions:

1. When a game announcement is posted, the bot adds 👍 and 👎 reactions
2. Players react with:
   - 👍 (or 🥏 or ✅) = Attending
   - 👎 (or ❌) = Not attending
   - All skin tone variations of thumbs up/down are supported
3. The bot automatically updates attendance in the database
4. Each reminder message shows current attendance status

**Note:** Only players with Discord IDs linked to their player profiles can use reaction-based attendance.

#### Manual attendance setting
Admins can manually set attendance:
```
!set_attendance game=GAME_ID player=PLAYER_ID status=yes
```

Status options: `yes`, `no`, `pending`

### 5. Useful Commands

#### Viewing Information
- `!schedule` - Show all upcoming games for tracked teams
- `!roster id=TEAM_ID` - Display team roster grouped by gender
- `!attendance game=GAME_ID` - Show attendance for a specific game
- `!info` - Display bot version and information

#### Editing
- `!edit_team id=TEAM_ID name="New Name" home_colour="red"` - Edit team details
- `!edit_player id=PLAYER_ID first="NewFirst" discord="newusername"` - Edit player details
- `!edit_game id=GAME_ID date="2025-06-20" time="18:00"` - Edit game details

#### Deleting (requires confirmation)
- `!delete_team id=TEAM_ID CONFIRM="Exact Team Name"`
- `!delete_player id=PLAYER_ID CONFIRM="First Last"`
- `!delete_game id=GAME_ID CONFIRM="YYYY-MM-DD"`
- `!remove_player_from_team player=PLAYER_ID team=TEAM_ID`

### 6. Troubleshooting

**Bot doesn't respond to commands:**
- Check that your Discord user ID is in the `privileged_users` list
- Verify the bot has permissions to read and send messages in the channel
- Check the logs at `logs/disco_robo.log`

**Game announcements not sending:**
- Verify the team is in the `tracked_teams` list (use `!track TEAM_ID`)
- Check that the `announcements` channel ID is correct in config.json
- Confirm the bot has permissions to post and add reactions in that channel

**Attendance reactions not working:**
- Ensure players have their Discord ID linked (check when creating players)
- Verify the bot has "Read Message History" and "Add Reactions" permissions
- The player must be on the team's roster

**Database errors:**
- Check that the database directory exists and is writable
- Verify the database file isn't corrupted (backup and restore if needed)
- Review logs for specific SQLAlchemy errors

## License
This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or
distribute this software, either in source code form or as a compiled
binary, for any purpose, commercial or non-commercial, and by any
means.

In jurisdictions that recognize copyright laws, the author or authors
of this software dedicate any and all copyright interest in the
software to the public domain. We make this dedication for the benefit
of the public at large and to the detriment of our heirs and
successors. We intend this dedication to be an overt act of
relinquishment in perpetuity of all present and future rights to this
software under copyright law.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

For more information, please refer to <https://unlicense.org/>