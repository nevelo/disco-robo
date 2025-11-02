# disco-robo
Discord robot for organizing disc.

## To use
This bot is designed to run in user mode on a Raspberry Pi. The database is
STORED LOCALLY and must be configured to be backed up or risk data loss!

** Raspberry Pi SD Cards are not reliable as storage media!! The are a KNOWN 
FAILURE RISK! **

### Initial Setup

#### Cloning the repo
TBD

#### Setting up the virtual environment
```python -m venv venv```
```pip install -r requirements.txt```

#### Connecting to your server

##### Giving Discord permissions to your bot
- writing your config/config.json file
- getting your DISCORD_TOKEN from Discord
- Getting CHANNEL_IDs
- 

##### Privileged users -- giving bot permissions to your users
To give a user access to the bot's control functions, paste their Discord uid
into a file at config/privileged_users.txt

### Building your database

#### Creating teams

#### Creating players

#### Adding players to teams

#### Adding games to teams

### Game reminders

### Attendance tracking

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